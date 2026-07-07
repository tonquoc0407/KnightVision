# Pre-Game Opening Outcome Predictor

## Dataset

- DuckDB warehouse: `warehouse/knightvision.duckdb`
- Rows: 9,431,205
- white_win: 4,673,397
- black_win: 4,378,076
- draw: 379,732

## Metrics

| Metric | Value |
|---|---:|
| accuracy | 0.4769 |
| balanced_accuracy | 0.4523 |
| macro_f1 | 0.4012 |
| weighted_f1 | 0.5364 |
| log_loss | 1.0195 |

## Classification Report

```text
              precision    recall  f1-score   support

   black_win     0.6442    0.4763    0.5477    875615
        draw     0.0535    0.3968    0.0943     75947
   white_win     0.6694    0.4839    0.5618    934679

    accuracy                         0.4769   1886241
   macro avg     0.4557    0.4523    0.4012   1886241
weighted avg     0.6329    0.4769    0.5364   1886241

```

## Top Features

| Feature | Importance |
|---|---:|
| `elo_diff` | 0.204336 |
| `abs_elo_diff` | 0.086412 |
| `time_control_type_bullet` | 0.060627 |
| `opening_variation_?` | 0.043866 |
| `eco_code_?` | 0.027051 |
| `opening_family_?` | 0.025155 |
| `black_elo` | 0.021248 |
| `white_elo` | 0.020213 |
| `base_time_seconds` | 0.013749 |
| `opening_family_King's Pawn` | 0.011968 |
| `opening_variation_King's Pawn` | 0.010853 |
| `increment_seconds` | 0.009722 |
| `opening_family_Sicilian Defense` | 0.008037 |
| `time_control_type_None` | 0.006713 |
| `opening_variation_King's Pawn Game` | 0.005993 |
