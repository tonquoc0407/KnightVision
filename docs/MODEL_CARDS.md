# ML Model Cards

These cards summarize the intended use, data, metrics, and limits of the three KnightVision ML case studies. The detailed generated cards live beside each artifact under `models/`.

## Blunder Prediction Under Time Pressure

| Field | Value |
|---|---|
| Artifact path | `models/blunder_predictor/` |
| Model type | XGBoost binary classifier |
| Prediction target | Whether a Stockfish-evaluated move is a standard 200 centipawn blunder |
| Source table | `analytics.blunder_positions` |
| Positive class | `is_blunder = true` |
| Main use | Rare-event screening and feature interpretation for time-pressure blunder risk |
| Not for | Real-time chess coaching, cheating detection, or player ranking |

Latest benchmark metrics:

| Metric | Value |
|---|---:|
| Training rows | 19,739 |
| Positive rows | 623 |
| ROC-AUC | 0.7558 |
| PR-AUC | 0.1009 |
| Precision | 0.0773 |
| Recall | 0.5680 |
| F1 | 0.1361 |

Notes:

- The target is imbalanced, so PR-AUC and recall are more informative than accuracy.
- Low precision is expected for rare-event screening; threshold tuning is required before using alerts.
- Output quality depends on Stockfish depth, sampling settings, and position coverage.

## Opening Outcome Prediction

| Field | Value |
|---|---|
| Artifact path | `models/opening_outcome/` |
| Model type | XGBoost multiclass classifier |
| Prediction target | `white_win`, `black_win`, or `draw` |
| Source table | `analytics.opening_stats` and Silver game features |
| Main use | Compare weak pre-game signals against stronger post-game diagnostic signals |
| Not for | Betting, deterministic result prediction, or claiming chess outcomes are predictable from opening alone |

Latest benchmark metrics:

| Model | Rows | Accuracy | Balanced Accuracy | Macro F1 | Weighted F1 | Log Loss |
|---|---:|---:|---:|---:|---:|---:|
| Pre-game | 322,164 | 0.3608 | 0.3981 | 0.3156 | 0.4195 | 1.0689 |
| Post-game diagnostic | 322,164 | 0.7584 | 0.7389 | 0.6245 | 0.8028 | 0.7664 |

Notes:

- The pre-game model is intentionally honest and weak-signal: Elo, opening, time control, and date do not determine the result.
- The post-game model uses parsed move metadata and should be described as diagnostic, not predictive before a game starts.
- Draws are relatively rare in the benchmark slice, so per-class metrics matter.

## Player Style Clustering

| Field | Value |
|---|---|
| Artifact path | `models/player_style_clusters/` |
| Model type | KMeans clustering with preprocessing and PCA visualization |
| Prediction target | None; unsupervised player style segments |
| Source table | Silver game/player behavior aggregates |
| Main use | Portfolio-friendly behavioral segmentation and exploratory analytics |
| Not for | Official player classification, skill ranking, or identity inference |

Latest benchmark metrics:

| Metric | Value |
|---|---:|
| Eligible players | 15,566 |
| Minimum games per player | 10 |
| Clusters | 5 |
| Silhouette score | 0.1372 |
| PCA explained variance, 2D | 0.3015 |

Generated labels:

- Blitz Specialists
- Opening Loyalists
- Opening Explorers
- Long-Game Grinders
- Sharp Tactical Players

Notes:

- Cluster names are human-readable labels assigned after inspecting feature profiles.
- A modest silhouette score is normal for behavior data with overlapping play styles.
- `cluster_assignments.csv` is generated locally and ignored by git because it contains public player identifiers.

## Shared Production Limits

- No scheduled retraining DAG is implemented yet.
- No model registry, artifact versioning, or drift monitoring is implemented.
- No online inference API is implemented.
- Models are case studies over benchmark data, not production decision systems.
