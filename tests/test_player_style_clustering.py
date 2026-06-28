from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("sklearn")

from ml.player_style_clustering.features import FEATURE_COLUMNS, split_identifiers_features  # noqa: E402
from ml.player_style_clustering.train import TrainingConfig, train  # noqa: E402


def player_feature_frame() -> pd.DataFrame:
    rows = []
    for index in range(30):
        cluster_hint = index % 3
        games = 12 + index
        rows.append(
            {
                "player": f"player_{index}",
                "games_played": games,
                "win_rate": [0.62, 0.42, 0.51][cluster_hint],
                "loss_rate": [0.32, 0.38, 0.46][cluster_hint],
                "draw_rate": [0.06, 0.20, 0.03][cluster_hint],
                "avg_elo": [1850, 1650, 1450][cluster_hint] + index,
                "elo_change_proxy": [80, 45, 120][cluster_hint],
                "avg_game_length": [34, 58, 26][cluster_hint],
                "avg_capture_count": [9, 5, 12][cluster_hint],
                "capture_game_rate": [0.92, 0.65, 0.96][cluster_hint],
                "castle_rate": [0.78, 0.91, 0.45][cluster_hint],
                "opening_diversity": [8, 4, 15][cluster_hint],
                "top_opening_share": [0.22, 0.55, 0.12][cluster_hint],
                "bullet_share": [0.10, 0.02, 0.62][cluster_hint],
                "blitz_share": [0.65, 0.28, 0.25][cluster_hint],
                "rapid_share": [0.20, 0.55, 0.10][cluster_hint],
                "classical_share": [0.05, 0.15, 0.03][cluster_hint],
                "clock_game_rate": [0.98, 0.88, 0.99][cluster_hint],
            }
        )
    return pd.DataFrame(rows)

def test_split_identifiers_features_validates_columns():
    identifiers, features = split_identifiers_features(player_feature_frame())

    assert list(identifiers.columns) == ["player", "games_played"]
    assert list(features.columns) == FEATURE_COLUMNS
    assert len(features) == 30

def test_train_writes_player_style_artifacts(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "ml.player_style_clustering.train.load_player_features",
        lambda _path, min_games: player_feature_frame()[lambda frame: frame["games_played"] >= min_games],
    )

    metadata = train(
        TrainingConfig(
            duckdb_path=Path("unused.duckdb"),
            output_dir=tmp_path,
            min_games=20,
            clusters=3,
            random_state=7,
            sweep_min_clusters=2,
            sweep_max_clusters=4,
        )
    )

    assert metadata["metrics"]["eligible_players"] == 22
    assert metadata["metrics"]["clusters"] == 3
    assert set(metadata["metrics"]) >= {"inertia", "silhouette_score", "pca_explained_variance_ratio"}
    assert [row["clusters"] for row in metadata["cluster_sweep"]] == [2, 3, 4]
    assert all(label for label in metadata["cluster_labels"].values())
    assert (tmp_path / "cluster_assignments.csv").exists()
    assert (tmp_path / "cluster_profiles.csv").exists()
    assert (tmp_path / "cluster_sweep.csv").exists()
    assert (tmp_path / "metrics.json").exists()
    assert (tmp_path / "model_card.md").exists()
    assert (tmp_path / "evaluation_report.md").exists()
    assert (tmp_path / "cluster_scatter.png").exists()
    assert (tmp_path / "feature_profiles.png").exists()
    assert (tmp_path / "elbow_plot.png").exists()
    assert (tmp_path / "silhouette_by_k.png").exists()
    assert (tmp_path / "preprocessing.joblib").exists()
    assert (tmp_path / "kmeans.joblib").exists()
    assert (tmp_path / "pca.joblib").exists()