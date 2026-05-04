# Train the KnightVision Stockfish blunder predictor

from __future__ import annotations

import argparse
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    classification_report,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBClassifier

from ml.blunder_predictor.features import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    load_training_frame,
    split_features_target,
)
from ml.common.reporting import write_json, write_model_card

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "knightvision-matplotlib"))
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

DEFAULT_DUCKDB_PATH = Path("warehouse/knightvision_benchmark.duckdb")
DEFAULT_OUTPUT_DIR = Path("models/blunder_predictor")

@dataclass(frozen=True)
class TrainingConfig:
    duckdb_path: Path = DEFAULT_DUCKDB_PATH
    output_dir: Path = DEFAULT_OUTPUT_DIR
    test_size: float = 0.2
    random_state: int = 42

def build_preprocessor() -> ColumnTransformer:
    numeric_pipeline = Pipeline([("imputer", SimpleImputer(strategy="median"))])
    categorical_pipeline = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )
    return ColumnTransformer(
        [
            ("numeric", numeric_pipeline, NUMERIC_FEATURES),
            ("categorical", categorical_pipeline, CATEGORICAL_FEATURES),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )

def build_classifier(y_train: pd.Series, *, random_state: int) -> XGBClassifier:
    negative = int((y_train == 0).sum())
    positive = int((y_train == 1).sum())
    scale_pos_weight = negative / positive if positive else 1.0
    return XGBClassifier(
        objective="binary:logistic",
        eval_metric="logloss",
        n_estimators=250,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        min_child_weight=1,
        reg_lambda=1.0,
        random_state=random_state,
        n_jobs=1,
        scale_pos_weight=scale_pos_weight,
    )

def validate_target(y: pd.Series) -> None:
    counts = y.value_counts()
    if len(counts) != 2:
        raise ValueError("training data must contain both blunder and non-blunder rows")
    if counts.min() < 2:
        raise ValueError("each target class needs at least two rows for stratified train/test split")

def compute_metrics(y_true: pd.Series, probabilities: pd.Series, predictions: pd.Series) -> dict[str, float]:
    return {
        "accuracy": float(accuracy_score(y_true, predictions)),
        "precision": float(precision_score(y_true, predictions, zero_division=0)),
        "recall": float(recall_score(y_true, predictions, zero_division=0)),
        "f1": float(f1_score(y_true, predictions, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, probabilities)),
        "pr_auc": float(average_precision_score(y_true, probabilities)),
    }

def baseline_metrics(X_test: pd.DataFrame, y_test: pd.Series) -> dict[str, dict[str, float]]:
    majority_predictions = pd.Series(0, index=y_test.index)
    majority_probabilities = pd.Series(0.0, index=y_test.index)
    low_time_predictions = ((X_test["time_remaining_seconds"].fillna(9999) <= 15) | (X_test["material_balance"].fillna(0) < -200)).astype(
        int
    )
    positive_rate = float(y_test.mean())
    prior_probabilities = pd.Series(positive_rate, index=y_test.index)
    return {
        "majority_class": compute_metrics(y_test, majority_probabilities, majority_predictions),
        "class_prior_probability": compute_metrics(y_test, prior_probabilities, majority_predictions),
        "low_time_or_material_rule": compute_metrics(y_test, low_time_predictions.astype(float), low_time_predictions),
    }

def threshold_metrics(y_true: pd.Series, probabilities: pd.Series) -> pd.DataFrame:
    rows = []
    for threshold in [index / 100 for index in range(5, 100, 5)]:
        predictions = (probabilities >= threshold).astype(int)
        rows.append(
            {
                "threshold": threshold,
                "precision": precision_score(y_true, predictions, zero_division=0),
                "recall": recall_score(y_true, predictions, zero_division=0),
                "f1": f1_score(y_true, predictions, zero_division=0),
            }
        )
    return pd.DataFrame(rows)

def write_curve_plots(y_true: pd.Series, probabilities: pd.Series, output_dir: Path) -> None:
    precision, recall, _ = precision_recall_curve(y_true, probabilities)
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(recall, precision, color="#2563eb")
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_title("Blunder Predictor Precision-Recall Curve")
    fig.tight_layout()
    fig.savefig(output_dir / "precision_recall_curve.png", dpi=160)
    plt.close(fig)

    fpr, tpr, _ = roc_curve(y_true, probabilities)
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(fpr, tpr, color="#0f766e")
    ax.plot([0, 1], [0, 1], color="#94a3b8", linestyle="--")
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title("Blunder Predictor ROC Curve")
    fig.tight_layout()
    fig.savefig(output_dir / "roc_curve.png", dpi=160)
    plt.close(fig)

def write_threshold_plot(frame: pd.DataFrame, output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(frame["threshold"], frame["precision"], label="precision", color="#2563eb")
    ax.plot(frame["threshold"], frame["recall"], label="recall", color="#dc2626")
    ax.plot(frame["threshold"], frame["f1"], label="f1", color="#0f766e")
    ax.set_xlabel("Threshold")
    ax.set_ylabel("Score")
    ax.set_title("Blunder Predictor Threshold Tradeoff")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)

def feature_importance_frame(preprocessor: ColumnTransformer, classifier: XGBClassifier) -> pd.DataFrame:
    return (
        pd.DataFrame(
            {
                "feature": preprocessor.get_feature_names_out(),
                "importance": classifier.feature_importances_,
            }
        )
        .sort_values("importance", ascending=False)
        .reset_index(drop=True)
    )

def write_feature_importance_plot(frame: pd.DataFrame, output_path: Path, *, limit: int = 20) -> None:
    top = frame.head(limit).sort_values("importance", ascending=True)
    fig, ax = plt.subplots(figsize=(8, max(4, len(top) * 0.28)))
    ax.barh(top["feature"], top["importance"], color="#2563eb")
    ax.set_xlabel("XGBoost importance")
    ax.set_ylabel("")
    ax.set_title("Top Blunder Predictor Features")
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)

def write_report(
    output_path: Path,
    *,
    config: TrainingConfig,
    row_count: int,
    class_counts: dict[int, int],
    metrics: dict[str, float],
    report_text: str,
    top_features: pd.DataFrame,
) -> None:
    lines = [
        "# Blunder Predictor Evaluation",
        "",
        "## Dataset",
        "",
        f"- DuckDB warehouse: `{config.duckdb_path}`",
        f"- Rows: {row_count:,}",
        f"- Non-blunders: {class_counts.get(0, 0):,}",
        f"- 200cp blunders: {class_counts.get(1, 0):,}",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "|---|---:|",
        *[f"| {name} | {value:.4f} |" for name, value in metrics.items()],
        "",
        "## Classification Report",
        "",
        "```text",
        report_text,
        "```",
        "",
        "## Top Features",
        "",
        "| Feature | Importance |",
        "|---|---:|",
        *[
            f"| `{row.feature}` | {row.importance:.6f} |"
            for row in top_features.head(15).itertuples(index=False)
        ],
        "",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")

def train(config: TrainingConfig) -> dict[str, object]:
    frame = load_training_frame(config.duckdb_path)
    X, y = split_features_target(frame)
    validate_target(y)

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=config.test_size,
        random_state=config.random_state,
        stratify=y,
    )

    preprocessor = build_preprocessor()
    X_train_encoded = preprocessor.fit_transform(X_train)
    X_test_encoded = preprocessor.transform(X_test)

    classifier = build_classifier(y_train, random_state=config.random_state)
    classifier.fit(X_train_encoded, y_train)

    probabilities = classifier.predict_proba(X_test_encoded)[:, 1]
    predictions = (probabilities >= 0.5).astype(int)
    metrics = compute_metrics(y_test, pd.Series(probabilities), pd.Series(predictions))
    baselines = baseline_metrics(X_test, y_test)
    thresholds = threshold_metrics(y_test, pd.Series(probabilities))
    report_text = classification_report(y_test, predictions, digits=4, zero_division=0)
    importance = feature_importance_frame(preprocessor, classifier)

    config.output_dir.mkdir(parents=True, exist_ok=True)
    classifier.save_model(config.output_dir / "model.json")
    joblib.dump(preprocessor, config.output_dir / "preprocessing.joblib")
    importance.to_csv(config.output_dir / "feature_importance.csv", index=False)
    thresholds.to_csv(config.output_dir / "threshold_metrics.csv", index=False)
    write_feature_importance_plot(importance, config.output_dir / "feature_importance.png")
    write_curve_plots(y_test, pd.Series(probabilities), config.output_dir)
    write_threshold_plot(thresholds, config.output_dir / "threshold_tradeoff.png")

    class_counts = {int(label): int(count) for label, count in y.value_counts().sort_index().items()}
    metadata = {
        "config": {key: str(value) if isinstance(value, Path) else value for key, value in asdict(config).items()},
        "row_count": int(len(frame)),
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "class_counts": class_counts,
        "features": {
            "numeric": NUMERIC_FEATURES,
            "categorical": CATEGORICAL_FEATURES,
            "encoded_count": int(len(preprocessor.get_feature_names_out())),
        },
        "metrics": metrics,
        "baselines": baselines,
        "recommended_threshold": 0.5,
    }
    write_json(config.output_dir / "metrics.json", metadata)
    write_report(
        config.output_dir / "evaluation_report.md",
        config=config,
        row_count=len(frame),
        class_counts=class_counts,
        metrics=metrics,
        report_text=report_text,
        top_features=importance,
    )
    write_model_card(
        config.output_dir / "model_card.md",
        title="Blunder Prediction Under Time Pressure",
        summary="Binary XGBoost classifier that ranks Stockfish-evaluated moves by likelihood of being a 200cp blunder.",
        dataset=[
            f"DuckDB warehouse: `{config.duckdb_path}`",
            f"Rows: {len(frame):,}",
            f"200cp blunders: {class_counts.get(1, 0):,}",
            f"Train/test split: {len(X_train):,}/{len(X_test):,}",
        ],
        metrics=metrics,
        artifacts=[
            "model.json",
            "preprocessing.joblib",
            "metrics.json",
            "threshold_metrics.csv",
            "precision_recall_curve.png",
            "roc_curve.png",
            "threshold_tradeoff.png",
            "feature_importance.csv",
            "feature_importance.png",
            "evaluation_report.md",
        ],
        extra_sections={
            "Baselines": [
                "| Baseline | ROC-AUC | PR-AUC | Precision | Recall | F1 |",
                "|---|---:|---:|---:|---:|---:|",
                *[
                    f"| {name} | {values['roc_auc']:.4f} | {values['pr_auc']:.4f} | {values['precision']:.4f} | {values['recall']:.4f} | {values['f1']:.4f} |"
                    for name, values in baselines.items()
                ],
            ]
        },
        limitations=[
            "Labels depend on sampled Stockfish evaluations, not every move in every game.",
            "Blunders are rare, so precision is low unless the decision threshold is tuned.",
            "The default threshold remains 0.5 for reproducibility; threshold_metrics.csv shows operating-point tradeoffs.",
        ],
        interpretation=[
            "Use ROC-AUC as the ranking-quality metric.",
            "Use PR-AUC and the threshold table when evaluating rare-event screening quality.",
            "Use higher thresholds when precision matters more than recall.",
        ],
    )
    return metadata

def main() -> None:
    parser = argparse.ArgumentParser(description="Train the KnightVision Stockfish blunder predictor.")
    parser.add_argument("--duckdb-path", type=Path, default=DEFAULT_DUCKDB_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()

    metadata = train(
        TrainingConfig(
            duckdb_path=args.duckdb_path,
            output_dir=args.output_dir,
            test_size=args.test_size,
            random_state=args.random_state,
        )
    )
    print(json.dumps(metadata["metrics"], indent=2, sort_keys=True))
    print(f"wrote blunder predictor artifacts to {args.output_dir}")

if __name__ == "__main__":
    main()