# Post-Game Opening Outcome Model Card

## Summary

Three-class XGBoost classifier for normalized game outcome. This variant is diagnostic only because it uses move-derived fields observed after the game.

## Dataset

- DuckDB warehouse: `warehouse/knightvision_benchmark.duckdb`
- Rows: 322,164
- white_win: 161,115
- black_win: 149,561
- draw: 11,488
- Train/test split: 257,731/64,433

## Metrics

| Metric | Value |
|---|---:|
| accuracy | 0.7584 |
| balanced_accuracy | 0.7389 |
| macro_f1 | 0.6245 |
| weighted_f1 | 0.8028 |
| log_loss | 0.7664 |

## Artifacts

- `model.json`
- `preprocessing.joblib`
- `label_encoder.joblib`
- `metrics.json`
- `confusion_matrix.csv`
- `confusion_matrix.png`
- `per_class_f1.csv`
- `per_class_f1.png`
- `feature_importance.csv`
- `feature_importance.png`
- `evaluation_report.md`

## Baselines

| Baseline | Accuracy | Balanced Accuracy | Macro F1 | Log Loss |
|---|---:|---:|---:|---:|
| majority_class | 0.5001 | 0.3333 | 0.2223 | 18.0182 |
| class_prior_probability | 0.5001 | 0.3333 | 0.2223 | 0.8217 |
| elo_favorite | 0.5360 | 0.3704 | 0.3636 | 16.7232 |

## Limitations

- Draws are rare in the benchmark slice, so class-balanced metrics matter more than raw accuracy.
- Opening outcome is weakly predictable before the game because player decisions and tactics dominate the final result.
- The post-game model must not be used as a pre-game predictor because it includes game metadata created after play.

## Recommended Interpretation

- Use the pre-game model for honest prediction claims.
- Use the post-game model only to explain how much signal exists in parsed game metadata.
- Compare against the majority, class-prior, and Elo-favorite baselines before making model quality claims.
