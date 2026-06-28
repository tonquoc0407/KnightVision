"""Read saved ML artifacts for dashboard presentation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = ROOT / "models"


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _read_markdown(path: Path, max_chars: int = 3000) -> str | None:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8").strip()
    return text[:max_chars]


def _read_csv(path: Path, limit: int = 20) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return pd.read_csv(path).head(limit).where(pd.notna, None).to_dict(orient="records")


def _asset(path: Path) -> str | None:
    if not path.exists():
        return None
    return "/model-artifacts/" + path.relative_to(MODELS_DIR).as_posix()


def blunder_artifacts() -> dict[str, Any]:
    root = MODELS_DIR / "blunder_predictor"
    return {
        "available": root.exists(),
        "title": "Blunder Prediction Under Time Pressure",
        "metrics": _read_json(root / "metrics.json") or {},
        "model_card": _read_markdown(root / "model_card.md"),
        "report": _read_markdown(root / "evaluation_report.md"),
        "feature_importance": _read_csv(root / "feature_importance.csv", limit=12),
        "threshold_metrics": _read_csv(root / "threshold_metrics.csv", limit=12),
        "assets": {
            "feature_importance": _asset(root / "feature_importance.png"),
            "precision_recall": _asset(root / "precision_recall_curve.png"),
            "roc": _asset(root / "roc_curve.png"),
            "threshold_tradeoff": _asset(root / "threshold_tradeoff.png"),
        },
    }


def opening_outcome_artifacts() -> dict[str, Any]:
    root = MODELS_DIR / "opening_outcome"
    models: dict[str, Any] = {}
    for name in ["pre_game", "post_game"]:
        model_root = root / name
        models[name] = {
            "available": model_root.exists(),
            "metrics": _read_json(model_root / "metrics.json") or {},
            "model_card": _read_markdown(model_root / "model_card.md"),
            "feature_importance": _read_csv(model_root / "feature_importance.csv", limit=12),
            "per_class_f1": _read_csv(model_root / "per_class_f1.csv", limit=10),
            "assets": {
                "feature_importance": _asset(model_root / "feature_importance.png"),
                "confusion_matrix": _asset(model_root / "confusion_matrix.png"),
                "per_class_f1": _asset(model_root / "per_class_f1.png"),
            },
        }
    return {
        "available": root.exists(),
        "title": "Opening Outcome Prediction",
        "metrics": _read_json(root / "metrics.json") or {},
        "comparison": _read_csv(root / "comparison_metrics.csv", limit=10),
        "report": _read_markdown(root / "comparison_report.md"),
        "models": models,
    }


def player_style_artifacts() -> dict[str, Any]:
    root = MODELS_DIR / "player_style_clusters"
    assignments = _read_csv(root / "cluster_assignments.csv", limit=50)
    return {
        "available": root.exists(),
        "title": "Player Style Clustering",
        "metrics": _read_json(root / "metrics.json") or {},
        "model_card": _read_markdown(root / "model_card.md"),
        "report": _read_markdown(root / "evaluation_report.md"),
        "cluster_profiles": _read_csv(root / "cluster_profiles.csv", limit=20),
        "cluster_sweep": _read_csv(root / "cluster_sweep.csv", limit=20),
        "sample_assignments": assignments,
        "assets": {
            "scatter": _asset(root / "cluster_scatter.png"),
            "feature_profiles": _asset(root / "feature_profiles.png"),
            "elbow": _asset(root / "elbow_plot.png"),
            "silhouette": _asset(root / "silhouette_by_k.png"),
        },
    }


def summary() -> dict[str, Any]:
    sections = [blunder_artifacts(), opening_outcome_artifacts(), player_style_artifacts()]
    return {
        "models_dir": str(MODELS_DIR),
        "available_count": sum(1 for section in sections if section["available"]),
        "sections": [
            {
                "title": section["title"],
                "available": section["available"],
                "metrics": section.get("metrics", {}),
            }
            for section in sections
        ],
    }
