# Post-Game Opening Outcome Model Card

## Summary

Three-class XGBoost classifier for normalized game outcome. This variant is diagnostic only because it uses move-derived fields observed after the game.

## Dataset

- DuckDB warehouse: `warehouse/knightvision.duckdb`
- Rows: 9,431,205
- white_win: 4,673,397
- black_win: 4,378,076
- draw: 379,732
- Train/test split: 7,544,964/1,886,241

## Metrics

| Metric | Value |
|---|---:|
| accuracy | 0.7115 |
| balanced_accuracy | 0.7106 |
| macro_f1 | 0.5970 |
| weighted_f1 | 0.7515 |
| log_loss | 0.7568 |

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
| majority_class | 0.4955 | 0.3333 | 0.2209 | 18.1831 |
| class_prior_probability | 0.4955 | 0.3333 | 0.2209 | 0.8335 |
| elo_favorite | 0.6143 | 0.4267 | 0.4178 | 13.9031 |

## Limitations

- Draws are rare in the benchmark slice, so class-balanced metrics matter more than raw accuracy.
- Opening outcome is weakly predictable before the game because player decisions and tactics dominate the final result.
- The post-game model must not be used as a pre-game predictor because it includes game metadata created after play.

## Recommended Interpretation

- Use the pre-game model for honest prediction claims.
- Use the post-game model only to explain how much signal exists in parsed game metadata.
- Compare against the majority, class-prior, and Elo-favorite baselines before making model quality claims.
