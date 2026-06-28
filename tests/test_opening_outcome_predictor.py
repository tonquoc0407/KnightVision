from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("xgboost")
pytest.importorskip("sklearn")

from ml.opening_outcome.features import PRE_GAME_NUMERIC_FEATURES, split_features_target  # noqa: E402
from ml.opening_outcome.train import TrainingConfig, train  # noqa: E402


def training_frame() -> pd.DataFrame:
    results = ["white_win", "black_win", "draw"]
    rows = []
    for index in range(90):
        result = results[index % len(results)]
        rows.append(
            {
                "result": result,
                "white_elo": 1400 + (index % 30) * 8,
                "black_elo": 1420 + (index % 20) * 7,
                "elo_diff": -20 + (index % 30) * 2,
                "abs_elo_diff": abs(-20 + (index % 30) * 2),
                "base_time_seconds": 180 if index % 2 else 600,
                "increment_seconds": 0 if index % 3 else 2,
                "year": 2026,
                "month": 4,
                "eco_code": f"C{index % 5:02d}",
                "opening_family": "Sicilian Defense" if index % 2 else "Queen's Pawn Game",
                "opening_variation": "Najdorf" if index % 4 else "London System",
                "time_control_type": "blitz" if index % 2 else "rapid",
                "game_length": 28 + (index % 35),
                "has_clock_data": int(index % 2 == 0),
                "has_capture": int(index % 3 != 0),
                "capture_count": index % 18,
                "white_castled": int(index % 4 != 0),
                "black_castled": int(index % 5 != 0),
                "legal_prefix_length": 20 + (index % 40),
            }
        )
    return pd.DataFrame(rows)

def test_split_features_target_uses_requested_feature_set():
    frame = training_frame()
    pre_game_X, y = split_features_target(frame, feature_set="pre_game")
    post_game_X, _ = split_features_target(frame, feature_set="post_game")

    assert list(pre_game_X.columns[: len(PRE_GAME_NUMERIC_FEATURES)]) == PRE_GAME_NUMERIC_FEATURES
    assert "game_length" not in pre_game_X.columns
    assert "game_length" in post_game_X.columns
    assert set(y.unique()) == {"white_win", "black_win", "draw"}

def test_train_writes_opening_outcome_artifacts(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("ml.opening_outcome.train.load_training_frame", lambda _path: training_frame())

    metadata = train(
        TrainingConfig(
            duckdb_path=Path("unused.duckdb"),
            output_dir=tmp_path,
            test_size=0.25,
            random_state=7,
        )
    )

    assert set(metadata["models"]) == {"pre_game", "post_game"}
    assert metadata["models"]["pre_game"]["row_count"] == 90
    assert metadata["models"]["post_game"]["class_counts"] == {"white_win": 30, "black_win": 30, "draw": 30}
    assert set(metadata["models"]["pre_game"]["baselines"]) == {
        "majority_class",
        "class_prior_probability",
        "elo_favorite",
    }
    for model_name in ["pre_game", "post_game"]:
        model_dir = tmp_path / model_name
        assert set(metadata["models"][model_name]["metrics"]) >= {"accuracy", "macro_f1", "weighted_f1", "log_loss"}
        assert (model_dir / "model.json").exists()
        assert (model_dir / "preprocessing.joblib").exists()
        assert (model_dir / "label_encoder.joblib").exists()
        assert (model_dir / "metrics.json").exists()
        assert (model_dir / "model_card.md").exists()
        assert (model_dir / "feature_importance.csv").exists()
        assert (model_dir / "feature_importance.png").exists()
        assert (model_dir / "confusion_matrix.csv").exists()
        assert (model_dir / "confusion_matrix.png").exists()
        assert (model_dir / "per_class_f1.csv").exists()
        assert (model_dir / "per_class_f1.png").exists()
        assert (model_dir / "evaluation_report.md").exists()

    assert (tmp_path / "comparison_metrics.csv").exists()
    assert (tmp_path / "comparison_report.md").exists()
    assert (tmp_path / "metrics.json").exists()