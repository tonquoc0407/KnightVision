# Player Style Clustering

## Summary

Unsupervised KMeans segmentation of players from behavior aggregates in `silver_games`.

## Dataset

- DuckDB warehouse: `warehouse/knightvision.duckdb`
- Eligible players: 130,863
- Minimum games per player: 10
- Default clusters: 5

## Metrics

| Metric | Value |
|---|---:|
| eligible_players | 130863 |
| clusters | 5 |
| inertia | 1247851.6156 |
| silhouette_score | 0.1827 |
| pca_explained_variance_ratio | 0.3897 |

## Artifacts

- `cluster_assignments.csv`
- `cluster_profiles.csv`
- `cluster_sweep.csv`
- `metrics.json`
- `cluster_scatter.png`
- `feature_profiles.png`
- `elbow_plot.png`
- `silhouette_by_k.png`
- `evaluation_report.md`
- `preprocessing.joblib`
- `kmeans.joblib`
- `pca.joblib`

## Cluster Sweep

| Clusters | Inertia | Silhouette Score |
|---:|---:|---:|
| 3 | 1473032.7042 | 0.1499 |
| 4 | 1345728.4991 | 0.1709 |
| 5 | 1247851.6156 | 0.1827 |
| 6 | 1225090.8933 | 0.1312 |
| 7 | 1129561.2836 | 0.1489 |
| 8 | 1084049.5176 | 0.1463 |

## Limitations

- Clusters are unsupervised behavioral segments, not ground-truth chess identities.
- Silhouette is expected to be modest because real player behavior overlaps heavily.
- Cluster labels are generated from relative feature profiles and should be treated as descriptive personas.

## Recommended Interpretation

- Use cluster_profiles.csv to understand each persona.
- Use cluster_sweep.csv plus elbow/silhouette plots when discussing why five clusters were retained.
- Use cluster_assignments.csv for player lookup or later dashboard integration.
