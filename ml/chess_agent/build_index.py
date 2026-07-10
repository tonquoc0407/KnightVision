"""Build the Chroma vector index from KnightVision DuckDB warehouse data."""

from __future__ import annotations

import argparse
from pathlib import Path

import chromadb
import duckdb

ROOT = Path(__file__).resolve().parents[2]
CHROMA_DIR = ROOT / "data" / "agent" / "chroma"
COLLECTION_NAME = "chess_knowledge"

_CHESS_CONCEPTS = [
    (
        "concept_eco",
        "ECO (Encyclopaedia of Chess Openings) codes classify chess openings into families. "
        "A-codes: flank openings (English, Reti, Bird). B-codes: semi-open games (Sicilian, Caro-Kann, French). "
        "C-codes: open games after 1.e4 e5 (Italian, Spanish, King's Gambit). "
        "D-codes: closed and semi-closed games (Queen's Gambit, Slav, Grunfeld). "
        "E-codes: Indian defenses (King's Indian, Nimzo-Indian, Queen's Indian).",
    ),
    (
        "concept_elo",
        "Elo rating measures chess player strength. Typical online ranges on Lichess: "
        "under 1000 beginner, 1000-1400 casual player, 1400-1800 intermediate, "
        "1800-2200 advanced club player, 2200-2500 candidate master or master, "
        "above 2500 grandmaster level. Lichess ratings are typically 200-400 points "
        "higher than over-the-board FIDE ratings. KnightVision groups players into "
        "200-point Elo buckets (800-1000, 1000-1200, ..., 2200+).",
    ),
    (
        "concept_blunder",
        "A blunder in chess is a serious mistake that worsens the position significantly. "
        "KnightVision defines a blunder as any move causing 200 or more centipawns (cp) "
        "of evaluation loss according to Stockfish 18 at depth 12. A centipawn is 1/100 "
        "of a pawn's material value. The blunder predictor model uses XGBoost trained on "
        "Stockfish-evaluated positions from December 2016 games.",
    ),
    (
        "concept_time_controls",
        "Chess time controls on Lichess: Bullet (under 3 minutes per player), "
        "Blitz (3-10 minutes), Rapid (10-60 minutes), Classical (over 60 minutes). "
        "KnightVision's December 2016 dataset has 0% clock coverage — Lichess did not "
        "record move times in PGN files in 2016, so time pressure analysis is unavailable "
        "for this dataset.",
    ),
    (
        "concept_game_phases",
        "Chess game phases used in KnightVision: opening (first 20 plies, moves 1-10), "
        "middlegame (plies 21-60, moves 11-30), endgame (plies beyond 60, move 30+). "
        "A ply is a single half-move (one player's turn). Game phase affects blunder rates "
        "and evaluation volatility.",
    ),
    (
        "concept_dataset",
        "KnightVision processes the Lichess public game database, available at lichess.org/db. "
        "The December 2016 (2016-12) dataset contains 9.4 million standard rated games "
        "from approximately 217,000 unique players. Pipeline layers: "
        "PGN download → Bronze (dedup) → Silver (ECO enrichment, normalization) → "
        "Gold (aggregations) → DuckDB warehouse → dbt analytics marts → FastAPI + React dashboard.",
    ),
    (
        "concept_result_distribution",
        "In the KnightVision December 2016 dataset: white wins approximately 38% of games, "
        "draws approximately 14%, black wins approximately 48%. The higher black win rate "
        "reflects the Lichess player population mix and online chess dynamics, where "
        "disconnections and time losses favor the opponent of the lagging player.",
    ),
    (
        "concept_pipeline_quality",
        "KnightVision silver quality gate requires at least 95% row retention from bronze. "
        "The December 2016 run achieved 99.87% retention (9.4M out of 9.4M games). "
        "Rejected rows (quarantine) go to data/quarantine/YYYY-MM/ as Parquet for replay. "
        "Quality metrics are stored as JSON under data/quality/YYYY-MM/.",
    ),
    (
        "concept_ml_models",
        "KnightVision includes three ML case studies: (1) Blunder predictor — XGBoost binary "
        "classifier, ROC-AUC 0.6884, trained on 47,733 Stockfish-evaluated positions. "
        "(2) Opening outcome — XGBoost multiclass (win/draw/loss), post-game accuracy 71.1% "
        "on 9.4M games. (3) Player style clustering — KMeans with 5 clusters over 130,863 "
        "eligible players, silhouette 0.1827. Clusters: Opening Explorers, Long-Game Grinders, "
        "Opening Loyalists, Balanced Generalists, Bullet Specialists.",
    ),
]


def _opening_docs(con: duckdb.DuckDBPyConnection) -> list[tuple[str, str]]:
    rows = con.execute(
        """
        SELECT eco_code, opening_family, elo_bucket, games_count,
               white_win_rate, draw_rate, black_win_rate, avg_game_length, time_control_type
        FROM analytics.opening_stats
        WHERE games_count >= 50
        ORDER BY games_count DESC
        LIMIT 3000
        """
    ).fetchall()

    docs = []
    for i, (eco, name, bucket, games, wwr, dr, bwr, avg_len, tc) in enumerate(rows):
        wwr = wwr or 0
        dr = dr or 0
        bwr = bwr or 0
        text = (
            f"Opening: {name} (ECO {eco}). Elo range: {bucket}. Time control: {tc}. "
            f"Analyzed from {games:,} games. "
            f"White wins {wwr * 100:.1f}%, draw {dr * 100:.1f}%, black wins {bwr * 100:.1f}%. "
            f"Average game length: {avg_len or 0:.0f} moves."
        )
        docs.append((f"op_{i}", text))
    return docs


def _player_docs(con: duckdb.DuckDBPyConnection) -> list[tuple[str, str]]:
    rows = con.execute(
        """
        SELECT player,
               sum(games_played) as total_games,
               round(avg(avg_elo)) as avg_elo,
               round(avg(win_rate) * 100, 1) as win_pct,
               any_value(most_played_opening_white) as white_open,
               any_value(most_played_opening_black) as black_open
        FROM analytics.player_profiles
        GROUP BY player
        HAVING total_games >= 30
        ORDER BY total_games DESC
        LIMIT 1000
        """
    ).fetchall()

    docs = []
    for i, (player, games, elo, win_pct, white_open, black_open) in enumerate(rows):
        parts = [f"Player: {player}. Games played: {games:,}. Average Elo: {elo:.0f}. Win rate: {win_pct:.1f}%."]
        if white_open:
            parts.append(f"Preferred opening as White: {white_open}.")
        if black_open:
            parts.append(f"Preferred opening as Black: {black_open}.")
        text = " ".join(parts)
        docs.append((f"pl_{i}", text))
    return docs


def build_index(duckdb_path: str, chroma_dir: Path = CHROMA_DIR) -> int:
    chroma_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(chroma_dir))

    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    collection = client.create_collection(COLLECTION_NAME)

    docs: list[tuple[str, str]] = list(_CHESS_CONCEPTS)

    con = duckdb.connect(duckdb_path, read_only=True)
    try:
        opening_docs = _opening_docs(con)
        docs.extend(opening_docs)
        print(f"  {len(opening_docs)} opening profiles indexed")
    except Exception as e:
        print(f"  Warning — could not index openings: {e}")

    try:
        player_docs = _player_docs(con)
        docs.extend(player_docs)
        print(f"  {len(player_docs)} player profiles indexed")
    except Exception as e:
        print(f"  Warning — could not index players: {e}")

    con.close()

    batch_size = 500
    for i in range(0, len(docs), batch_size):
        batch = docs[i : i + batch_size]
        collection.add(ids=[d[0] for d in batch], documents=[d[1] for d in batch])

    print(f"Chroma index built: {len(docs)} documents → {chroma_dir}")
    return len(docs)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the KnightVision Chroma vector index.")
    parser.add_argument("--duckdb-path", default=str(ROOT / "warehouse" / "knightvision.duckdb"))
    parser.add_argument("--chroma-dir", type=Path, default=CHROMA_DIR)
    args = parser.parse_args()
    build_index(args.duckdb_path, args.chroma_dir)


if __name__ == "__main__":
    main()
