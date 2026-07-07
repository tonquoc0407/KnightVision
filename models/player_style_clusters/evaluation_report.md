# Player Style Clustering Evaluation

Player style clusters are unsupervised statistical segments built from per-player behavior features in `silver_games`. Style labels are descriptive summaries of cluster profiles, not ground-truth chess identities.

## Dataset

- DuckDB warehouse: `warehouse/knightvision.duckdb`
- Eligible players: 130,863
- Minimum games per player: 10
- Clusters: 5

## Metrics

| Metric | Value |
|---|---:|
| eligible_players | 130863 |
| clusters | 5 |
| inertia | 1247851.6156 |
| silhouette_score | 0.1827 |
| pca_explained_variance_ratio | 0.3897 |

## Cluster Profiles

| Cluster | Style Label | Players | Win Rate | Draw Rate | Avg Elo | Avg Length | Top Opening Share | Blitz Share |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | Opening Explorers | 47,239 | 0.5014 | 0.0443 | 1694.2 | 68.8 | 0.1655 | 0.8877 |
| 1 | Long-Game Grinders | 39,230 | 0.5034 | 0.0460 | 1622.2 | 65.8 | 0.1906 | 0.0788 |
| 2 | Opening Loyalists | 24,418 | 0.2858 | 0.0268 | 1321.1 | 51.4 | 0.2169 | 0.3418 |
| 3 | Balanced Generalists | 4,578 | 0.4793 | 0.0493 | 1508.1 | 59.0 | 0.2029 | 0.0273 |
| 4 | Bullet Specialists | 15,398 | 0.5116 | 0.0356 | 1767.2 | 68.7 | 0.1828 | 0.1457 |
