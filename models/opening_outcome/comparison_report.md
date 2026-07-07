# Opening Outcome Model Comparison

Two XGBoost classifiers are trained from `silver_games`: a pre-game model using only information known before play starts, and a post-game diagnostic model that also includes move-count and parsed game features.

- DuckDB warehouse: `warehouse/knightvision.duckdb`
- Output directory: `models/opening_outcome`

## Metrics

| Model | Accuracy | Balanced Accuracy | Macro F1 | Weighted F1 | Log Loss |
|---|---:|---:|---:|---:|---:|
| pre_game | 0.4769 | 0.4523 | 0.4012 | 0.5364 | 1.0195 |
| post_game | 0.7115 | 0.7106 | 0.5970 | 0.7515 | 0.7568 |

## Feature Sets

| Model | Numeric Features | Categorical Features | Encoded Features |
|---|---:|---:|---:|
| pre_game | 8 | 4 | 3129 |
| post_game | 15 | 4 | 3136 |

## Interpretation

The pre-game model is the usable prediction case because it avoids result leakage. The post-game model is diagnostic: it estimates how much additional signal parsed move metadata contributes after the game has already been played.

Metric columns included: accuracy, balanced_accuracy, macro_f1, weighted_f1, log_loss.
