# Post-Game Opening Outcome Predictor

## Dataset

- DuckDB warehouse: `warehouse/knightvision.duckdb`
- Rows: 9,431,205
- white_win: 4,673,397
- black_win: 4,378,076
- draw: 379,732

## Metrics

| Metric | Value |
|---|---:|
| accuracy | 0.7115 |
| balanced_accuracy | 0.7106 |
| macro_f1 | 0.5970 |
| weighted_f1 | 0.7515 |
| log_loss | 0.7568 |

## Classification Report

```text
              precision    recall  f1-score   support

   black_win     0.8429    0.7083    0.7698    875615
        draw     0.1485    0.7088    0.2456     75947
   white_win     0.8477    0.7147    0.7756    934679

    accuracy                         0.7115   1886241
   macro avg     0.6130    0.7106    0.5970   1886241
weighted avg     0.8173    0.7115    0.7515   1886241

```

## Top Features

| Feature | Importance |
|---|---:|
| `game_length` | 0.223296 |
| `legal_prefix_length` | 0.163514 |
| `capture_count` | 0.111952 |
| `elo_diff` | 0.080746 |
| `abs_elo_diff` | 0.076060 |
| `has_capture` | 0.038906 |
| `opening_variation_King's Pawn` | 0.029465 |
| `opening_family_King's Pawn` | 0.027303 |
| `black_castled` | 0.026890 |
| `opening_family_Queen's Pawn` | 0.024426 |
| `opening_variation_Queen's Pawn` | 0.023907 |
| `time_control_type_classical` | 0.018837 |
| `white_castled` | 0.018798 |
| `time_control_type_bullet` | 0.017370 |
| `base_time_seconds` | 0.015940 |
