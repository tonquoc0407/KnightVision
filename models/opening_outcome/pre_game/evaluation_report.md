# Pre-Game Opening Outcome Predictor

## Dataset

- DuckDB warehouse: `warehouse/knightvision_benchmark.duckdb`
- Rows: 322,164
- white_win: 161,115
- black_win: 149,561
- draw: 11,488

## Metrics

| Metric | Value |
|---|---:|
| accuracy | 0.3608 |
| balanced_accuracy | 0.3981 |
| macro_f1 | 0.3156 |
| weighted_f1 | 0.4195 |
| log_loss | 1.0689 |

## Classification Report

```text
              precision    recall  f1-score   support

   black_win     0.5374    0.3388    0.4156     29912
        draw     0.0461    0.4830    0.0841      2298
   white_win     0.5588    0.3725    0.4470     32223

    accuracy                         0.3608     64433
   macro avg     0.3807    0.3981    0.3156     64433
weighted avg     0.5305    0.3608    0.4195     64433

```

## Top Features

| Feature | Importance |
|---|---:|
| `time_control_type_bullet` | 0.027977 |
| `opening_variation_Englund Gambit` | 0.007903 |
| `elo_diff` | 0.007137 |
| `opening_variation_Caro-Kann Defense: Main Line` | 0.006466 |
| `opening_family_Barnes Defense` | 0.005578 |
| `opening_variation_Italian Game: Giuoco Pianissimo, Italian Four Knights Variation` | 0.005417 |
| `opening_variation_Englund Gambit Declined: Reversed Alekhine` | 0.005294 |
| `opening_variation_King's Indian Defense: Normal Variation` | 0.005285 |
| `black_elo` | 0.005173 |
| `abs_elo_diff` | 0.005101 |
| `time_control_type_rapid` | 0.005067 |
| `opening_variation_Ruy Lopez: Berlin Defense` | 0.005019 |
| `opening_family_Modern Defense` | 0.005013 |
| `eco_code_E70` | 0.005003 |
| `eco_code_E67` | 0.004977 |
