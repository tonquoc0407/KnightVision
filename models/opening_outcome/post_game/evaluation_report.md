# Post-Game Opening Outcome Predictor

## Dataset

- DuckDB warehouse: `warehouse/knightvision_benchmark.duckdb`
- Rows: 322,164
- white_win: 161,115
- black_win: 149,561
- draw: 11,488

## Metrics

| Metric | Value |
|---|---:|
| accuracy | 0.7584 |
| balanced_accuracy | 0.7389 |
| macro_f1 | 0.6245 |
| weighted_f1 | 0.8028 |
| log_loss | 0.7664 |

## Classification Report

```text
              precision    recall  f1-score   support

   black_win     0.9130    0.7420    0.8187     29912
        draw     0.1346    0.6967    0.2256      2298
   white_win     0.8880    0.7779    0.8293     32223

    accuracy                         0.7584     64433
   macro avg     0.6452    0.7389    0.6245     64433
weighted avg     0.8727    0.7584    0.8028     64433

```

## Top Features

| Feature | Importance |
|---|---:|
| `legal_prefix_length` | 0.099273 |
| `game_length` | 0.067230 |
| `capture_count` | 0.030144 |
| `has_capture` | 0.013608 |
| `elo_diff` | 0.012007 |
| `opening_family_Petrov's Defense` | 0.009993 |
| `abs_elo_diff` | 0.009039 |
| `opening_variation_Rapport-Jobava System, with e6` | 0.008583 |
| `time_control_type_bullet` | 0.008452 |
| `opening_variation_Indian Defense: Wade-Tartakower Defense` | 0.008310 |
| `eco_code_D03` | 0.007966 |
| `opening_variation_Caro-Kann Defense: Panov Attack, Modern Defense` | 0.007497 |
| `eco_code_D12` | 0.007283 |
| `eco_code_C29` | 0.007160 |
| `opening_variation_Danish Gambit Accepted: Copenhagen Defense` | 0.006841 |
