# Blunder Prediction Under Time Pressure

## Summary

Binary XGBoost classifier that ranks Stockfish-evaluated moves by likelihood of being a 200cp blunder.

## Dataset

- DuckDB warehouse: `warehouse/knightvision_benchmark.duckdb`
- Rows: 19,739
- 200cp blunders: 623
- Train/test split: 15,791/3,948

## Metrics

| Metric | Value |
|---|---:|
| accuracy | 0.7718 |
| precision | 0.0773 |
| recall | 0.5680 |
| f1 | 0.1361 |
| roc_auc | 0.7558 |
| pr_auc | 0.1009 |

## Artifacts

- `model.json`
- `preprocessing.joblib`
- `metrics.json`
- `threshold_metrics.csv`
- `precision_recall_curve.png`
- `roc_curve.png`
- `threshold_tradeoff.png`
- `feature_importance.csv`
- `feature_importance.png`
- `evaluation_report.md`

## Baselines

| Baseline | ROC-AUC | PR-AUC | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|
| majority_class | 0.5000 | 0.0317 | 0.0000 | 0.0000 | 0.0000 |
| class_prior_probability | 0.5000 | 0.0317 | 0.0000 | 0.0000 | 0.0000 |
| low_time_or_material_rule | 0.5163 | 0.0333 | 0.0524 | 0.0800 | 0.0633 |

## Limitations

- Labels depend on sampled Stockfish evaluations, not every move in every game.
- Blunders are rare, so precision is low unless the decision threshold is tuned.
- The default threshold remains 0.5 for reproducibility; threshold_metrics.csv shows operating-point tradeoffs.

## Recommended Interpretation

- Use ROC-AUC as the ranking-quality metric.
- Use PR-AUC and the threshold table when evaluating rare-event screening quality.
- Use higher thresholds when precision matters more than recall.
