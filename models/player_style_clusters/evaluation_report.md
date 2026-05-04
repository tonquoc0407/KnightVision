# Player Style Clustering Evaluation

Player style clusters are unsupervised statistical segments built from per-player behavior features in `silver_games`. Style labels are descriptive summaries of cluster profiles, not ground-truth chess identities.

## Dataset

- DuckDB warehouse: `warehouse/knightvision_benchmark.duckdb`
- Eligible players: 15,566
- Minimum games per player: 10
- Clusters: 5

## Metrics

| Metric | Value |
|---|---:|
| eligible_players | 15566 |
| clusters | 5 |
| inertia | 178156.4354 |
| silhouette_score | 0.1372 |
| pca_explained_variance_ratio | 0.3015 |

## Cluster Profiles

| Cluster | Style Label | Players | Win Rate | Draw Rate | Avg Elo | Avg Length | Top Opening Share | Blitz Share |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | Blitz Specialists | 3,250 | 0.4449 | 0.0208 | 1510.4 | 60.6 | 0.2573 | 0.9756 |
| 1 | Opening Loyalists | 3,145 | 0.4650 | 0.0134 | 1505.1 | 55.8 | 0.2824 | 0.0393 |
| 2 | Opening Explorers | 4,313 | 0.5230 | 0.0363 | 2008.7 | 71.9 | 0.2382 | 0.0220 |
| 3 | Long-Game Grinders | 1,218 | 0.4879 | 0.0431 | 1521.0 | 63.9 | 0.2488 | 0.0278 |
| 4 | Sharp Tactical Players | 3,640 | 0.5303 | 0.0601 | 1841.3 | 77.9 | 0.2322 | 0.9710 |
