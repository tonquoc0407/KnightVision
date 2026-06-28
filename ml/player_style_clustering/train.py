# Train KnightVision player style clusters

from __future__ import annotations

import argparse
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

import joblib
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer
from sklearn.metrics import silhouette_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ml.common.reporting import write_json, write_model_card
from ml.player_style_clustering.features import FEATURE_COLUMNS, load_player_features, split_identifiers_features

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "knightvision-matplotlib"))
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

DEFAULT_DUCKDB_PATH = Path("warehouse/knightvision_benchmark.duckdb")
DEFAULT_OUTPUT_DIR = Path("models/player_style_clusters")

@dataclass(frozen=True)
class TrainingConfig:
    duckdb_path: Path = DEFAULT_DUCKDB_PATH
    output_dir: Path = DEFAULT_OUTPUT_DIR
    min_games: int = 10
    clusters: int = 5
    random_state: int = 42
    sweep_min_clusters: int = 3
    sweep_max_clusters: int = 8

def build_preprocessor() -> Pipeline:
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )

def build_clusterer(config: TrainingConfig) -> KMeans:
    return KMeans(n_clusters=config.clusters, random_state=config.random_state, n_init="auto")

def validate_training_frame(frame: pd.DataFrame, config: TrainingConfig) -> None:
    if frame.empty:
        raise ValueError("player style training frame is empty")
    if config.clusters < 2:
        raise ValueError("clusters must be at least 2")
    if len(frame) < config.clusters:
        raise ValueError("eligible player count must be at least the requested cluster count")

def style_label_candidates(profile: pd.Series) -> list[tuple[str, float]]:
    """Return ranked readable personas from z-scored cluster traits."""

    candidates = [
        ("Bullet Specialists", profile.get("bullet_share", 0.0)),
        ("Blitz Specialists", profile.get("blitz_share", 0.0)),
        ("Long-Game Grinders", profile.get("avg_game_length", 0.0) + profile.get("draw_rate", 0.0)),
        ("Opening Loyalists", profile.get("top_opening_share", 0.0)),
        ("Opening Explorers", profile.get("opening_diversity", 0.0) - profile.get("top_opening_share", 0.0)),
        ("Sharp Tactical Players", profile.get("capture_game_rate", 0.0) + profile.get("avg_capture_count", 0.0)),
        ("High-Elo Regulars", profile.get("avg_elo", 0.0)),
        ("Decisive Winners", profile.get("win_rate", 0.0) - profile.get("draw_rate", 0.0)),
        ("Balanced Generalists", -abs(profile.get("win_rate", 0.0)) - abs(profile.get("top_opening_share", 0.0))),
    ]
    return sorted(candidates, key=lambda item: item[1], reverse=True)

def assign_style_labels(profile_frame: pd.DataFrame) -> dict[int, str]:
    zscores = profile_frame[FEATURE_COLUMNS].copy()
    std = zscores.std(ddof=0).replace(0, 1)
    zscores = (zscores - zscores.mean()) / std
    labels: dict[int, str] = {}
    used: set[str] = set()
    for cluster, row in zscores.iterrows():
        candidates = style_label_candidates(row)
        label = next((candidate for candidate, score in candidates if candidate not in used and score > 0), "Balanced Generalists")
        if label in used:
            label = next(candidate for candidate, _score in candidates if candidate not in used)
        labels[int(cluster)] = label
        used.add(label)
    return labels

def profile_clusters(assignments: pd.DataFrame) -> pd.DataFrame:
    profiles = assignments.groupby("cluster", as_index=True)[FEATURE_COLUMNS].mean()
    profiles.insert(0, "cluster_size", assignments.groupby("cluster").size())
    labels = assign_style_labels(profiles)
    profiles.insert(0, "style_label", profiles.index.map(labels))
    return profiles.reset_index()

def write_scatter(assignments: pd.DataFrame, output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 6))
    for cluster, group in assignments.groupby("cluster"):
        ax.scatter(group["pca_x"], group["pca_y"], s=8, alpha=0.55, label=str(cluster))
    ax.set_title("Player Style Clusters")
    ax.set_xlabel("PCA 1")
    ax.set_ylabel("PCA 2")
    ax.legend(title="Cluster", markerscale=2)
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)

def write_profile_plot(profile_frame: pd.DataFrame, output_path: Path) -> None:
    plot_features = [
        "win_rate",
        "draw_rate",
        "avg_game_length",
        "avg_capture_count",
        "castle_rate",
        "opening_diversity",
        "top_opening_share",
        "bullet_share",
        "blitz_share",
        "rapid_share",
    ]
    normalized = profile_frame.set_index("style_label")[plot_features]
    std = normalized.std(ddof=0).replace(0, 1)
    normalized = (normalized - normalized.mean()) / std

    fig, ax = plt.subplots(figsize=(10, max(4, len(normalized) * 0.6)))
    image = ax.imshow(normalized, aspect="auto", cmap="vlag" if "vlag" in plt.colormaps() else "coolwarm")
    ax.set_xticks(range(len(plot_features)), labels=plot_features, rotation=45, ha="right")
    ax.set_yticks(range(len(normalized)), labels=normalized.index)
    ax.set_title("Cluster Feature Profile Z-Scores")
    fig.colorbar(image, ax=ax, fraction=0.035, pad=0.02)
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)

def cluster_sweep(encoded, config: TrainingConfig) -> pd.DataFrame:
    rows = []
    max_clusters = min(config.sweep_max_clusters, len(encoded) - 1)
    for cluster_count in range(config.sweep_min_clusters, max_clusters + 1):
        clusterer = KMeans(n_clusters=cluster_count, random_state=config.random_state, n_init="auto")
        labels = clusterer.fit_predict(encoded)
        rows.append(
            {
                "clusters": cluster_count,
                "inertia": float(clusterer.inertia_),
                "silhouette_score": float(silhouette_score(encoded, labels)) if len(set(labels)) > 1 else 0.0,
            }
        )
    return pd.DataFrame(rows)

def write_sweep_plots(sweep: pd.DataFrame, output_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(sweep["clusters"], sweep["inertia"], marker="o", color="#2563eb")
    ax.set_xlabel("Clusters")
    ax.set_ylabel("Inertia")
    ax.set_title("Player Style Clustering Elbow Plot")
    fig.tight_layout()
    fig.savefig(output_dir / "elbow_plot.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(sweep["clusters"], sweep["silhouette_score"], marker="o", color="#0f766e")
    ax.set_xlabel("Clusters")
    ax.set_ylabel("Silhouette Score")
    ax.set_title("Player Style Clustering Silhouette By K")
    fig.tight_layout()
    fig.savefig(output_dir / "silhouette_by_k.png", dpi=160)
    plt.close(fig)

def write_report(
    output_path: Path,
    *,
    config: TrainingConfig,
    row_count: int,
    metrics: dict[str, float | int],
    profiles: pd.DataFrame,
) -> None:
    lines = [
        "# Player Style Clustering Evaluation",
        "",
        "Player style clusters are unsupervised statistical segments built from per-player behavior features in `silver_games`. Style labels are descriptive summaries of cluster profiles, not ground-truth chess identities.",
        "",
        "## Dataset",
        "",
        f"- DuckDB warehouse: `{config.duckdb_path}`",
        f"- Eligible players: {row_count:,}",
        f"- Minimum games per player: {config.min_games}",
        f"- Clusters: {config.clusters}",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "|---|---:|",
        *[f"| {name} | {value:.4f} |" if isinstance(value, float) else f"| {name} | {value} |" for name, value in metrics.items()],
        "",
        "## Cluster Profiles",
        "",
        "| Cluster | Style Label | Players | Win Rate | Draw Rate | Avg Elo | Avg Length | Top Opening Share | Blitz Share |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in profiles.itertuples(index=False):
        lines.append(
            f"| {row.cluster} | {row.style_label} | {row.cluster_size:,} | "
            f"{row.win_rate:.4f} | {row.draw_rate:.4f} | {row.avg_elo:.1f} | "
            f"{row.avg_game_length:.1f} | {row.top_opening_share:.4f} | {row.blitz_share:.4f} |"
        )
    lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")

def train(config: TrainingConfig) -> dict[str, object]:
    frame = load_player_features(config.duckdb_path, min_games=config.min_games)
    validate_training_frame(frame, config)
    identifiers, features = split_identifiers_features(frame)

    preprocessor = build_preprocessor()
    encoded = preprocessor.fit_transform(features)
    sweep = cluster_sweep(encoded, config)
    clusterer = build_clusterer(config)
    clusters = clusterer.fit_predict(encoded)

    pca = PCA(n_components=2, random_state=config.random_state)
    coordinates = pca.fit_transform(encoded)

    assignments = identifiers.copy()
    assignments["cluster"] = clusters
    for column in FEATURE_COLUMNS:
        assignments[column] = features[column].to_numpy()
    profiles = profile_clusters(assignments)
    style_map = dict(zip(profiles["cluster"], profiles["style_label"], strict=True))
    assignments["style_label"] = assignments["cluster"].map(style_map)
    assignments["pca_x"] = coordinates[:, 0]
    assignments["pca_y"] = coordinates[:, 1]

    metrics = {
        "eligible_players": int(len(assignments)),
        "clusters": int(config.clusters),
        "inertia": float(clusterer.inertia_),
        "silhouette_score": float(silhouette_score(encoded, clusters)) if len(set(clusters)) > 1 else 0.0,
        "pca_explained_variance_ratio": float(pca.explained_variance_ratio_.sum()),
    }

    config.output_dir.mkdir(parents=True, exist_ok=True)
    assignments.to_csv(config.output_dir / "cluster_assignments.csv", index=False)
    profiles.to_csv(config.output_dir / "cluster_profiles.csv", index=False)
    sweep.to_csv(config.output_dir / "cluster_sweep.csv", index=False)
    joblib.dump(preprocessor, config.output_dir / "preprocessing.joblib")
    joblib.dump(clusterer, config.output_dir / "kmeans.joblib")
    joblib.dump(pca, config.output_dir / "pca.joblib")
    write_scatter(assignments, config.output_dir / "cluster_scatter.png")
    write_profile_plot(profiles, config.output_dir / "feature_profiles.png")
    write_sweep_plots(sweep, config.output_dir)

    metadata = {
        "config": {key: str(value) if isinstance(value, Path) else value for key, value in asdict(config).items()},
        "features": FEATURE_COLUMNS,
        "metrics": metrics,
        "cluster_sweep": sweep.to_dict(orient="records"),
        "cluster_labels": {str(key): value for key, value in style_map.items()},
    }
    write_json(config.output_dir / "metrics.json", metadata)
    write_report(
        config.output_dir / "evaluation_report.md",
        config=config,
        row_count=len(assignments),
        metrics=metrics,
        profiles=profiles,
    )
    write_model_card(
        config.output_dir / "model_card.md",
        title="Player Style Clustering",
        summary="Unsupervised KMeans segmentation of players from behavior aggregates in `silver_games`.",
        dataset=[
            f"DuckDB warehouse: `{config.duckdb_path}`",
            f"Eligible players: {len(assignments):,}",
            f"Minimum games per player: {config.min_games}",
            f"Default clusters: {config.clusters}",
        ],
        metrics=metrics,
        artifacts=[
            "cluster_assignments.csv",
            "cluster_profiles.csv",
            "cluster_sweep.csv",
            "metrics.json",
            "cluster_scatter.png",
            "feature_profiles.png",
            "elbow_plot.png",
            "silhouette_by_k.png",
            "evaluation_report.md",
            "preprocessing.joblib",
            "kmeans.joblib",
            "pca.joblib",
        ],
        extra_sections={
            "Cluster Sweep": [
                "| Clusters | Inertia | Silhouette Score |",
                "|---:|---:|---:|",
                *[
                    f"| {int(row.clusters)} | {row.inertia:.4f} | {row.silhouette_score:.4f} |"
                    for row in sweep.itertuples(index=False)
                ],
            ]
        },
        limitations=[
            "Clusters are unsupervised behavioral segments, not ground-truth chess identities.",
            "Silhouette is expected to be modest because real player behavior overlaps heavily.",
            "Cluster labels are generated from relative feature profiles and should be treated as descriptive personas.",
        ],
        interpretation=[
            "Use cluster_profiles.csv to understand each persona.",
            "Use cluster_sweep.csv plus elbow/silhouette plots when discussing why five clusters were retained.",
            "Use cluster_assignments.csv for player lookup or later dashboard integration.",
        ],
    )
    return metadata

def main() -> None:
    parser = argparse.ArgumentParser(description="Train KnightVision player style clusters.")
    parser.add_argument("--duckdb-path", type=Path, default=DEFAULT_DUCKDB_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--min-games", type=int, default=10)
    parser.add_argument("--clusters", type=int, default=5)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()

    metadata = train(
        TrainingConfig(
            duckdb_path=args.duckdb_path,
            output_dir=args.output_dir,
            min_games=args.min_games,
            clusters=args.clusters,
            random_state=args.random_state,
        )
    )
    print(json.dumps(metadata["metrics"], indent=2, sort_keys=True))
    print(f"wrote player style cluster artifacts to {args.output_dir}")

if __name__ == "__main__":
    main()