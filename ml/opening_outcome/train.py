# Train KnightVision opening outcome predictors

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
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    log_loss,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, OneHotEncoder
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

from ml.common.reporting import write_json, write_model_card
from ml.opening_outcome.features import (
    FEATURE_SETS,
    RESULT_LABELS,
    load_training_frame,
    split_features_target,
)

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "knightvision-matplotlib"))
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

DEFAULT_DUCKDB_PATH = Path("warehouse/knightvision_benchmark.duckdb")
DEFAULT_OUTPUT_DIR = Path("models/opening_outcome")

@dataclass(frozen=True)
class TrainingConfig:
    duckdb_path: Path = DEFAULT_DUCKDB_PATH
    output_dir: Path = DEFAULT_OUTPUT_DIR
    test_size: float = 0.2
    random_state: int = 42

def build_preprocessor(numeric_features: list[str], categorical_features: list[str]) -> ColumnTransformer:
    numeric_pipeline = Pipeline([("imputer", SimpleImputer(strategy="median"))])
    categorical_pipeline = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="most_frequent")),
            (
                "onehot",
                OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=25, sparse_output=True),
            ),
        ]
    )
    return ColumnTransformer(
        [
            ("numeric", numeric_pipeline, numeric_features),
            ("categorical", categorical_pipeline, categorical_features),
        ],
        remainder="drop",
        sparse_threshold=0.8,
        verbose_feature_names_out=False,
    )

def build_classifier(*, num_classes: int, random_state: int) -> XGBClassifier:
    return XGBClassifier(
        objective="multi:softprob",
        eval_metric="mlogloss",
        num_class=num_classes,
        n_estimators=180,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        min_child_weight=1,
        reg_lambda=1.0,
        random_state=random_state,
        n_jobs=1,
    )

def validate_target(y: pd.Series) -> None:
    counts = y.value_counts()
    missing = [label for label in RESULT_LABELS if label not in counts]
    if missing:
        raise ValueError(f"training data is missing outcome classes: {', '.join(missing)}")
    if counts.min() < 2:
        raise ValueError("each outcome class needs at least two rows for stratified train/test split")

def compute_metrics(y_true: pd.Series, probabilities: pd.DataFrame, predictions: pd.Series) -> dict[str, float]:
    return {
        "accuracy": float(accuracy_score(y_true, predictions)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, predictions)),
        "macro_f1": float(f1_score(y_true, predictions, average="macro", zero_division=0)),
        "weighted_f1": float(f1_score(y_true, predictions, average="weighted", zero_division=0)),
        "log_loss": float(log_loss(y_true, probabilities, labels=list(range(probabilities.shape[1])))),
    }

def baseline_metrics(X_test: pd.DataFrame, y_test: pd.Series, *, num_classes: int) -> dict[str, dict[str, float]]:
    majority_class = int(y_test.value_counts().idxmax())
    majority_predictions = pd.Series(majority_class, index=y_test.index)
    majority_probabilities = pd.DataFrame(0.0, index=y_test.index, columns=range(num_classes))
    majority_probabilities[majority_class] = 1.0

    prior = y_test.value_counts(normalize=True).reindex(range(num_classes), fill_value=0.0)
    prior_probabilities = pd.DataFrame([prior.to_list()] * len(y_test), index=y_test.index, columns=range(num_classes))

    elo_predictions = pd.Series(
        [
            2 if white_elo >= black_elo else 0
            for white_elo, black_elo in zip(X_test["white_elo"].fillna(0), X_test["black_elo"].fillna(0), strict=True)
        ],
        index=y_test.index,
    )
    elo_probabilities = pd.DataFrame(0.0, index=y_test.index, columns=range(num_classes))
    for row_index, prediction in elo_predictions.items():
        elo_probabilities.loc[row_index, prediction] = 1.0

    return {
        "majority_class": compute_metrics(y_test, majority_probabilities, majority_predictions),
        "class_prior_probability": compute_metrics(y_test, prior_probabilities, majority_predictions),
        "elo_favorite": compute_metrics(y_test, elo_probabilities, elo_predictions),
    }

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

def write_feature_importance_plot(frame: pd.DataFrame, output_path: Path, *, title: str, limit: int = 20) -> None:
    top = frame.head(limit).sort_values("importance", ascending=True)
    fig, ax = plt.subplots(figsize=(8, max(4, len(top) * 0.28)))
    ax.barh(top["feature"], top["importance"], color="#0f766e")
    ax.set_xlabel("XGBoost importance")
    ax.set_ylabel("")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)

def write_confusion_heatmap(confusion: pd.DataFrame, output_path: Path, *, title: str) -> None:
    fig, ax = plt.subplots(figsize=(6, 5))
    image = ax.imshow(confusion, cmap="Blues")
    ax.set_xticks(range(len(confusion.columns)), labels=confusion.columns, rotation=30, ha="right")
    ax.set_yticks(range(len(confusion.index)), labels=confusion.index)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
    ax.set_title(title)
    for row_index, row_label in enumerate(confusion.index):
        for col_index, col_label in enumerate(confusion.columns):
            ax.text(col_index, row_index, int(confusion.loc[row_label, col_label]), ha="center", va="center")
    fig.colorbar(image, ax=ax, fraction=0.04, pad=0.02)
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)

def per_class_f1_frame(y_true: pd.Series, predictions: pd.Series, classes: list[str]) -> pd.DataFrame:
    report = classification_report(y_true, predictions, target_names=classes, output_dict=True, zero_division=0)
    return pd.DataFrame(
        [{"class": label, "f1": float(report[label]["f1-score"])} for label in classes]
    )

def write_per_class_f1_plot(frame: pd.DataFrame, output_path: Path, *, title: str) -> None:
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(frame["class"], frame["f1"], color="#0f766e")
    ax.set_ylim(0, 1)
    ax.set_ylabel("F1")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)

def write_evaluation_report(
    output_path: Path,
    *,
    model_name: str,
    config: TrainingConfig,
    row_count: int,
    class_counts: dict[str, int],
    metrics: dict[str, float],
    report_text: str,
    top_features: pd.DataFrame,
) -> None:
    title = "Pre-Game Opening Outcome Predictor" if model_name == "pre_game" else "Post-Game Opening Outcome Predictor"
    lines = [
        f"# {title}",
        "",
        "## Dataset",
        "",
        f"- DuckDB warehouse: `{config.duckdb_path}`",
        f"- Rows: {row_count:,}",
        *[f"- {label}: {class_counts.get(label, 0):,}" for label in RESULT_LABELS],
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

def train_one_model(frame: pd.DataFrame, *, model_name: str, config: TrainingConfig) -> dict[str, object]:
    spec = FEATURE_SETS[model_name]
    numeric_features = list(spec["numeric"])
    categorical_features = list(spec["categorical"])
    X, y = split_features_target(frame, feature_set=model_name)
    validate_target(y)

    encoder = LabelEncoder()
    encoder.fit(RESULT_LABELS)
    y_encoded = pd.Series(encoder.transform(y), index=y.index)

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y_encoded,
        test_size=config.test_size,
        random_state=config.random_state,
        stratify=y_encoded,
    )

    preprocessor = build_preprocessor(numeric_features, categorical_features)
    X_train_encoded = preprocessor.fit_transform(X_train)
    X_test_encoded = preprocessor.transform(X_test)

    classifier = build_classifier(num_classes=len(encoder.classes_), random_state=config.random_state)
    sample_weight = compute_sample_weight(class_weight="balanced", y=y_train)
    classifier.fit(X_train_encoded, y_train, sample_weight=sample_weight)

    probabilities = classifier.predict_proba(X_test_encoded)
    predictions = classifier.predict(X_test_encoded)
    metrics = compute_metrics(y_test, pd.DataFrame(probabilities), pd.Series(predictions))
    baselines = baseline_metrics(X_test, y_test, num_classes=len(encoder.classes_))
    report_text = classification_report(y_test, predictions, target_names=encoder.classes_, digits=4, zero_division=0)
    confusion = pd.DataFrame(
        confusion_matrix(y_test, predictions, labels=list(range(len(encoder.classes_)))),
        index=encoder.classes_,
        columns=encoder.classes_,
    )
    per_class_f1 = per_class_f1_frame(y_test, pd.Series(predictions), list(encoder.classes_))
    importance = feature_importance_frame(preprocessor, classifier)

    output_dir = config.output_dir / model_name
    output_dir.mkdir(parents=True, exist_ok=True)
    classifier.save_model(output_dir / "model.json")
    joblib.dump(preprocessor, output_dir / "preprocessing.joblib")
    joblib.dump(encoder, output_dir / "label_encoder.joblib")
    importance.to_csv(output_dir / "feature_importance.csv", index=False)
    confusion.to_csv(output_dir / "confusion_matrix.csv")
    per_class_f1.to_csv(output_dir / "per_class_f1.csv", index=False)
    write_feature_importance_plot(
        importance,
        output_dir / "feature_importance.png",
        title=f"Top {model_name.replace('_', ' ').title()} Outcome Features",
    )
    write_confusion_heatmap(confusion, output_dir / "confusion_matrix.png", title=f"{model_name.replace('_', ' ').title()} Confusion Matrix")
    write_per_class_f1_plot(per_class_f1, output_dir / "per_class_f1.png", title=f"{model_name.replace('_', ' ').title()} Per-Class F1")

    class_counts = {str(label): int(count) for label, count in y.value_counts().reindex(RESULT_LABELS, fill_value=0).items()}
    metadata = {
        "config": {key: str(value) if isinstance(value, Path) else value for key, value in asdict(config).items()},
        "model_name": model_name,
        "row_count": int(len(y)),
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "class_counts": class_counts,
        "features": {
            "numeric": numeric_features,
            "categorical": categorical_features,
            "encoded_count": int(len(preprocessor.get_feature_names_out())),
        },
        "classes": list(encoder.classes_),
        "metrics": metrics,
        "baselines": baselines,
    }
    write_json(output_dir / "metrics.json", metadata)
    write_evaluation_report(
        output_dir / "evaluation_report.md",
        model_name=model_name,
        config=config,
        row_count=len(y),
        class_counts=class_counts,
        metrics=metrics,
        report_text=report_text,
        top_features=importance,
    )
    diagnostic = model_name == "post_game"
    model_title = "Post-Game Opening Outcome" if diagnostic else "Pre-Game Opening Outcome"
    write_model_card(
        output_dir / "model_card.md",
        title=f"{model_title} Model Card",
        summary=(
            "Three-class XGBoost classifier for normalized game outcome. "
            + ("This variant is diagnostic only because it uses move-derived fields observed after the game." if diagnostic else "This variant uses only pre-game features and is the honest prediction case.")
        ),
        dataset=[
            f"DuckDB warehouse: `{config.duckdb_path}`",
            f"Rows: {len(y):,}",
            *[f"{label}: {class_counts.get(label, 0):,}" for label in RESULT_LABELS],
            f"Train/test split: {len(X_train):,}/{len(X_test):,}",
        ],
        metrics=metrics,
        artifacts=[
            "model.json",
            "preprocessing.joblib",
            "label_encoder.joblib",
            "metrics.json",
            "confusion_matrix.csv",
            "confusion_matrix.png",
            "per_class_f1.csv",
            "per_class_f1.png",
            "feature_importance.csv",
            "feature_importance.png",
            "evaluation_report.md",
        ],
        extra_sections={
            "Baselines": [
                "| Baseline | Accuracy | Balanced Accuracy | Macro F1 | Log Loss |",
                "|---|---:|---:|---:|---:|",
                *[
                    f"| {name} | {values['accuracy']:.4f} | {values['balanced_accuracy']:.4f} | {values['macro_f1']:.4f} | {values['log_loss']:.4f} |"
                    for name, values in baselines.items()
                ],
            ]
        },
        limitations=[
            "Draws are rare in the benchmark slice, so class-balanced metrics matter more than raw accuracy.",
            "Opening outcome is weakly predictable before the game because player decisions and tactics dominate the final result.",
            "The post-game model must not be used as a pre-game predictor because it includes game metadata created after play.",
        ],
        interpretation=[
            "Use the pre-game model for honest prediction claims.",
            "Use the post-game model only to explain how much signal exists in parsed game metadata.",
            "Compare against the majority, class-prior, and Elo-favorite baselines before making model quality claims.",
        ],
    )
    return metadata

def write_comparison_report(output_path: Path, *, config: TrainingConfig, models: dict[str, dict[str, object]]) -> None:
    metric_names = ["accuracy", "balanced_accuracy", "macro_f1", "weighted_f1", "log_loss"]
    lines = [
        "# Opening Outcome Model Comparison",
        "",
        "Two XGBoost classifiers are trained from `silver_games`: a pre-game model using only information known before play starts, and a post-game diagnostic model that also includes move-count and parsed game features.",
        "",
        f"- DuckDB warehouse: `{config.duckdb_path}`",
        f"- Output directory: `{config.output_dir}`",
        "",
        "## Metrics",
        "",
        "| Model | Accuracy | Balanced Accuracy | Macro F1 | Weighted F1 | Log Loss |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for model_name, metadata in models.items():
        metrics = metadata["metrics"]
        lines.append(
            f"| {model_name} | "
            f"{metrics['accuracy']:.4f} | "
            f"{metrics['balanced_accuracy']:.4f} | "
            f"{metrics['macro_f1']:.4f} | "
            f"{metrics['weighted_f1']:.4f} | "
            f"{metrics['log_loss']:.4f} |"
        )

    lines.extend(
        [
            "",
            "## Feature Sets",
            "",
            "| Model | Numeric Features | Categorical Features | Encoded Features |",
            "|---|---:|---:|---:|",
        ]
    )
    for model_name, metadata in models.items():
        features = metadata["features"]
        lines.append(
            f"| {model_name} | {len(features['numeric'])} | {len(features['categorical'])} | {features['encoded_count']} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "The pre-game model is the usable prediction case because it avoids result leakage. The post-game model is diagnostic: it estimates how much additional signal parsed move metadata contributes after the game has already been played.",
            "",
            "Metric columns included: " + ", ".join(metric_names) + ".",
            "",
        ]
    )
    output_path.write_text("\n".join(lines), encoding="utf-8")

def write_comparison_metrics(output_path: Path, models: dict[str, dict[str, object]]) -> None:
    rows = []
    for model_name, metadata in models.items():
        row = {"model": model_name}
        row.update(metadata["metrics"])
        rows.append(row)
    pd.DataFrame(rows).to_csv(output_path, index=False)

def train(config: TrainingConfig) -> dict[str, object]:
    frame = load_training_frame(config.duckdb_path)
    if frame.empty:
        raise ValueError("opening outcome training frame is empty")

    config.output_dir.mkdir(parents=True, exist_ok=True)
    models = {
        "pre_game": train_one_model(frame, model_name="pre_game", config=config),
        "post_game": train_one_model(frame, model_name="post_game", config=config),
    }
    write_comparison_report(config.output_dir / "comparison_report.md", config=config, models=models)
    write_comparison_metrics(config.output_dir / "comparison_metrics.csv", models)

    metadata = {
        "config": {key: str(value) if isinstance(value, Path) else value for key, value in asdict(config).items()},
        "models": models,
    }
    write_json(config.output_dir / "metrics.json", metadata)
    return metadata

def main() -> None:
    parser = argparse.ArgumentParser(description="Train KnightVision opening outcome predictors.")
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
    print(json.dumps({name: model["metrics"] for name, model in metadata["models"].items()}, indent=2, sort_keys=True))
    print(f"wrote opening outcome artifacts to {args.output_dir}")

if __name__ == "__main__":
    main()