# Blunder Predictor Evaluation

## Dataset

- DuckDB warehouse: `warehouse/knightvision.duckdb`
- Rows: 59,667
- Non-blunders: 55,325
- 200cp blunders: 4,342

## Metrics

| Metric | Value |
|---|---:|
| accuracy | 0.5721 |
| precision | 0.1102 |
| recall | 0.6901 |
| f1 | 0.1900 |
| roc_auc | 0.6884 |
| pr_auc | 0.1372 |

## Classification Report

```text
              precision    recall  f1-score   support

           0     0.9586    0.5628    0.7092     11066
           1     0.1102    0.6901    0.1900       868

    accuracy                         0.5721     11934
   macro avg     0.5344    0.6264    0.4496     11934
weighted avg     0.8969    0.5721    0.6715     11934

```

## Top Features

| Feature | Importance |
|---|---:|
| `game_phase_opening` | 0.062089 |
| `ply_number` | 0.056710 |
| `game_phase_middlegame` | 0.030664 |
| `game_phase_endgame` | 0.023196 |
| `player_elo` | 0.019824 |
| `time_control_type_bullet` | 0.018659 |
| `is_in_check` | 0.018491 |
| `time_control_type_blitz` | 0.018373 |
| `square_h6` | 0.018228 |
| `square_f7` | 0.018127 |
| `material_balance` | 0.017805 |
| `square_d5` | 0.017764 |
| `square_e5` | 0.017216 |
| `square_c6` | 0.016693 |
| `square_f3` | 0.016060 |
