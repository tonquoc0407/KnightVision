# Opening Outcome Model Comparison

Two XGBoost classifiers are trained from `silver_games`: a pre-game model using only information known before play starts, and a post-game diagnostic model that also includes move-count and parsed game features.

- DuckDB warehouse: `warehouse/knightvision_benchmark.duckdb`
- Output directory: `models/opening_outcome`

## Metrics

| Model | Accuracy | Balanced Accuracy | Macro F1 | Weighted F1 | Log Loss |
|---|---:|---:|---:|---:|---:|
| pre_game | 0.3608 | 0.3981 | 0.3156 | 0.4195 | 1.0689 |
| post_game | 0.7584 | 0.7389 | 0.6245 | 0.8028 | 0.7664 |

## Feature Sets

| Model | Numeric Features | Categorical Features | Encoded Features |
|---|---:|---:|---:|
| pre_game | 8 | 4 | 1267 |
| post_game | 15 | 4 | 1274 |

## Interpretation

The pre-game model is the usable prediction case because it avoids result leakage. The post-game model is diagnostic: it estimates how much additional signal parsed move metadata contributes after the game has already been played.

Metric columns included: accuracy, balanced_accuracy, macro_f1, weighted_f1, log_loss.
