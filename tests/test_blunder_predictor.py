from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("xgboost")
pytest.importorskip("sklearn")

from ml.blunder_predictor.features import FEATURE_COLUMNS, split_features_target  # noqa: E402
from ml.blunder_predictor.train import TrainingConfig, train  # noqa: E402


def training_frame() -> pd.DataFrame:
    rows = []
    for index in range(40):
        is_blunder = index % 5 == 0
        rows.append(
            {
                "is_blunder": int(is_blunder),
                "player_elo": 1500 + index,
                "time_remaining_seconds": 3 if is_blunder else 90,
                "ply_number": index + 1,
                "material_balance": -300 if is_blunder else 100,
                "is_in_check": int(index % 7 == 0),
                "year": 2026,
                "game_phase": "opening" if index < 20 else "middlegame",
                "time_control_type": "bullet" if index % 3 == 0 else "blitz",
                "square": "f3" if is_blunder else "e4",
            }
        )
    return pd.DataFrame(rows)

def test_split_features_target_validates_required_columns():
    X, y = split_features_target(training_frame())
    assert list(X.columns) == FEATURE_COLUMNS
    assert set(y.unique()) == {0, 1}

def test_train_writes_model_artifacts(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("ml.blunder_predictor.train.load_training_frame", lambda _path: training_frame())

    metadata = train(
        TrainingConfig(
            duckdb_path=Path("unused.duckdb"),
            output_dir=tmp_path,
            test_size=0.25,
            random_state=7,
        )
    )

    assert metadata["row_count"] == 40
    assert metadata["class_counts"] == {0: 32, 1: 8}
    assert set(metadata["metrics"]) >= {"accuracy", "precision", "recall", "f1", "roc_auc", "pr_auc"}
    assert set(metadata["baselines"]) == {"majority_class", "class_prior_probability", "low_time_or_material_rule"}
    assert (tmp_path / "model.json").exists()
    assert (tmp_path / "preprocessing.joblib").exists()
    assert (tmp_path / "metrics.json").exists()
    assert (tmp_path / "model_card.md").exists()
    assert (tmp_path / "threshold_metrics.csv").exists()
    assert (tmp_path / "precision_recall_curve.png").exists()
    assert (tmp_path / "roc_curve.png").exists()
    assert (tmp_path / "threshold_tradeoff.png").exists()
    assert (tmp_path / "feature_importance.csv").exists()
    assert (tmp_path / "feature_importance.png").exists()
    assert (tmp_path / "evaluation_report.md").exists()