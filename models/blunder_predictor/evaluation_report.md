# Blunder Predictor Evaluation

## Dataset

- DuckDB warehouse: `warehouse/knightvision_benchmark.duckdb`
- Rows: 19,739
- Non-blunders: 19,116
- 200cp blunders: 623

## Metrics

| Metric | Value |
|---|---:|
| accuracy | 0.7718 |
| precision | 0.0773 |
| recall | 0.5680 |
| f1 | 0.1361 |
| roc_auc | 0.7558 |
| pr_auc | 0.1009 |

## Classification Report

```text
              precision    recall  f1-score   support

           0     0.9822    0.7784    0.8685      3823
           1     0.0773    0.5680    0.1361       125

    accuracy                         0.7718      3948
   macro avg     0.5298    0.6732    0.5023      3948
weighted avg     0.9535    0.7718    0.8453      3948

```

## Top Features

| Feature | Importance |
|---|---:|
| `ply_number` | 0.053962 |
| `time_control_type_bullet` | 0.041405 |
| `square_f7` | 0.035228 |
| `player_elo` | 0.026209 |
| `square_d7` | 0.023713 |
| `square_g4` | 0.023537 |
| `square_e3` | 0.022809 |
| `square_c6` | 0.022421 |
| `time_remaining_seconds` | 0.022047 |
| `square_d5` | 0.022011 |
| `square_b4` | 0.021060 |
| `square_d3` | 0.020187 |
| `square_e4` | 0.020159 |
| `square_f2` | 0.020063 |
| `square_g5` | 0.019051 |
