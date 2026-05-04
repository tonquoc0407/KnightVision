# Player Style Clustering

## Summary

Unsupervised KMeans segmentation of players from behavior aggregates in `silver_games`.

## Dataset

- DuckDB warehouse: `warehouse/knightvision_benchmark.duckdb`
- Eligible players: 15,566
- Minimum games per player: 10
- Default clusters: 5

## Metrics

| Metric | Value |
|---|---:|
| eligible_players | 15566 |
| clusters | 5 |
| inertia | 178156.4354 |
| silhouette_score | 0.1372 |
| pca_explained_variance_ratio | 0.3015 |

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
| 3 | 200769.9710 | 0.1490 |
| 4 | 186535.3958 | 0.1688 |
| 5 | 178156.4354 | 0.1372 |
| 6 | 165641.5295 | 0.1396 |
| 7 | 156230.4607 | 0.1389 |
| 8 | 150374.5187 | 0.1348 |

## Limitations

- Clusters are unsupervised behavioral segments, not ground-truth chess identities.
- Silhouette is expected to be modest because real player behavior overlaps heavily.
- Cluster labels are generated from relative feature profiles and should be treated as descriptive personas.

## Recommended Interpretation

- Use cluster_profiles.csv to understand each persona.
- Use cluster_sweep.csv plus elbow/silhouette plots when discussing why five clusters were retained.
- Use cluster_assignments.csv for player lookup or later dashboard integration.
