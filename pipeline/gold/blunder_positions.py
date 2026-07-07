# Build Stockfish-backed `gold/blunder_positions` from Silver games.

# The Spark job samples games first, then opens one Stockfish process per Spark
# partition. Unit tests exercise the pure evaluation path with a fake evaluator,
# so the default test suite does not require a Stockfish binary.

from __future__ import annotations

import argparse
import os
import shutil
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chess
import chess.engine
from pyspark.sql import Row
from pyspark.sql import functions as F
from pyspark.sql import types as T

from pipeline.spark_session import build_spark

MATE_SCORE_CP = 100_000
DEFAULT_BLUNDER_THRESHOLD_CP = 200

BLUNDER_SCHEMA = T.StructType(
    [
        T.StructField("game_id", T.StringType()),
        T.StructField("ply_number", T.IntegerType()),
        T.StructField("fen", T.StringType()),
        T.StructField("move_uci", T.StringType()),
        T.StructField("square", T.StringType()),
        T.StructField("game_phase", T.StringType()),
        T.StructField("time_control_type", T.StringType()),
        T.StructField("year", T.IntegerType()),
        T.StructField("player_elo", T.IntegerType()),
        T.StructField("time_remaining_seconds", T.IntegerType()),
        T.StructField("material_balance", T.IntegerType()),
        T.StructField("is_in_check", T.BooleanType()),
        T.StructField("eval_before_cp", T.IntegerType()),
        T.StructField("eval_after_cp", T.IntegerType()),
        T.StructField("cp_loss", T.IntegerType()),
        T.StructField("is_blunder", T.BooleanType()),
    ]
)

PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
}

@dataclass(frozen=True)
class EngineConfig:
    path: str
    depth: int | None = 12
    movetime_ms: int | None = None

class StockfishEvaluator:
    def __init__(self, config: EngineConfig) -> None:
        self._engine = chess.engine.SimpleEngine.popen_uci(config.path)
        if config.movetime_ms is not None:
            self._limit = chess.engine.Limit(time=config.movetime_ms / 1000)
        else:
            self._limit = chess.engine.Limit(depth=config.depth)

    def evaluate(self, board: chess.Board, pov: chess.Color) -> int:
        info = self._engine.analyse(board, self._limit)
        return int(info["score"].pov(pov).score(mate_score=MATE_SCORE_CP))

    def close(self) -> None:
        self._engine.quit()

def game_phase_from_ply(ply_number: int) -> str:
    if ply_number <= 20:
        return "opening"
    if ply_number <= 60:
        return "middlegame"
    return "endgame"

def material_balance_cp(board: chess.Board, pov: chess.Color) -> int:
    white = 0
    black = 0
    for piece_type, value in PIECE_VALUES.items():
        white += len(board.pieces(piece_type, chess.WHITE)) * value
        black += len(board.pieces(piece_type, chess.BLACK)) * value
    balance = white - black
    return balance if pov == chess.WHITE else -balance

def score_loss(before_cp: int, after_cp: int) -> int:
    return max(0, before_cp - after_cp)

def player_elo_for_turn(game: dict[str, Any], turn: chess.Color) -> int | None:
    return game.get("white_elo") if turn == chess.WHITE else game.get("black_elo")

def evaluate_game_positions(
    game: dict[str, Any],
    evaluator: Callable[[chess.Board, chess.Color], int],
    *,
    max_plies: int | None = 80,
    blunder_threshold_cp: int = DEFAULT_BLUNDER_THRESHOLD_CP,
) -> list[dict[str, Any]]:
    board = chess.Board()
    rows: list[dict[str, Any]] = []
    moves = game.get("moves_uci") or []
    clock_seconds = game.get("clock_seconds") or []

    for ply_index, move_uci in enumerate(moves):
        if max_plies is not None and ply_index >= max_plies:
            break
        try:
            move = chess.Move.from_uci(move_uci)
        except ValueError:
            break
        if move not in board.legal_moves:
            break

        mover = board.turn
        fen = board.fen()
        eval_before_cp = evaluator(board, mover)
        material_balance = material_balance_cp(board, mover)
        is_in_check = board.is_check()
        board.push(move)
        eval_after_cp = evaluator(board, mover)
        cp_loss = score_loss(eval_before_cp, eval_after_cp)
        ply_number = ply_index + 1

        rows.append(
            {
                "game_id": game.get("game_id"),
                "ply_number": ply_number,
                "fen": fen,
                "move_uci": move_uci,
                "square": chess.square_name(move.to_square),
                "game_phase": game_phase_from_ply(ply_number),
                "time_control_type": game.get("time_control_type"),
                "year": game.get("year"),
                "player_elo": player_elo_for_turn(game, mover),
                "time_remaining_seconds": clock_seconds[ply_index] if ply_index < len(clock_seconds) else None,
                "material_balance": material_balance,
                "is_in_check": is_in_check,
                "eval_before_cp": eval_before_cp,
                "eval_after_cp": eval_after_cp,
                "cp_loss": cp_loss,
                "is_blunder": cp_loss >= blunder_threshold_cp,
            }
        )

    return rows

def _row_to_game(row: Row) -> dict[str, Any]:
    game = row.asDict(recursive=True)
    return {
        "game_id": game.get("game_id"),
        "moves_uci": game.get("moves_uci") or [],
        "clock_seconds": game.get("clock_seconds") or [],
        "time_control_type": game.get("time_control_type"),
        "year": game.get("year"),
        "white_elo": game.get("white_elo"),
        "black_elo": game.get("black_elo"),
    }

def _evaluate_partition(
    rows: Iterable[Row],
    *,
    config: EngineConfig,
    max_plies: int | None,
    blunder_threshold_cp: int,
) -> Iterator[dict[str, Any]]:
    evaluator = StockfishEvaluator(config)
    try:
        for row in rows:
            yield from evaluate_game_positions(
                _row_to_game(row),
                evaluator.evaluate,
                max_plies=max_plies,
                blunder_threshold_cp=blunder_threshold_cp,
            )
    finally:
        evaluator.close()

def build_blunder_positions(
    silver_df,
    *,
    stockfish_path: str,
    fraction: float = 0.01,
    seed: int = 42,
    max_games: int | None = None,
    max_plies: int | None = 80,
    depth: int | None = 12,
    movetime_ms: int | None = None,
    blunder_threshold_cp: int = DEFAULT_BLUNDER_THRESHOLD_CP,
):
    if not stockfish_path:
        raise ValueError("stockfish_path is required for engine-backed blunder analytics")
    if fraction <= 0 or fraction > 1:
        raise ValueError("fraction must be in the range (0, 1]")

    selected = silver_df.filter(F.size("moves_uci") > 0).sample(withReplacement=False, fraction=fraction, seed=seed)
    if max_games is not None:
        selected = selected.limit(max_games)

    columns = ["game_id", "moves_uci", "clock_seconds", "time_control_type", "year", "white_elo", "black_elo"]
    sampled = selected.select(*(column for column in columns if column in selected.columns))
    config = EngineConfig(path=stockfish_path, depth=depth, movetime_ms=movetime_ms)
    rdd = sampled.rdd.mapPartitions(
        lambda rows: _evaluate_partition(
            rows,
            config=config,
            max_plies=max_plies,
            blunder_threshold_cp=blunder_threshold_cp,
        )
    )
    return silver_df.sparkSession.createDataFrame(rdd, BLUNDER_SCHEMA)

def resolve_stockfish_path(value: str | None) -> str:
    path = value or os.getenv("STOCKFISH_PATH")
    if not path:
        raise ValueError("Provide --stockfish-path or set STOCKFISH_PATH.")
    resolved = shutil.which(path) if os.path.basename(path) == path else path
    if resolved is None or not Path(resolved).exists():
        raise FileNotFoundError(f"Stockfish binary not found: {path}")
    if not os.access(resolved, os.X_OK):
        raise PermissionError(f"Stockfish binary is not executable: {resolved}")
    return resolved

def run(
    input_path: str,
    output_path: str,
    *,
    stockfish_path: str,
    fraction: float = 0.01,
    seed: int = 42,
    max_games: int | None = None,
    max_plies: int | None = 80,
    depth: int | None = 12,
    movetime_ms: int | None = None,
    blunder_threshold_cp: int = DEFAULT_BLUNDER_THRESHOLD_CP,
) -> None:
    spark = build_spark("KnightVision Gold Blunder Positions", master="local[5]")
    try:
        build_blunder_positions(
            spark.read.parquet(input_path),
            stockfish_path=stockfish_path,
            fraction=fraction,
            seed=seed,
            max_games=max_games,
            max_plies=max_plies,
            depth=depth,
            movetime_ms=movetime_ms,
            blunder_threshold_cp=blunder_threshold_cp,
        ).write.mode("overwrite").parquet(output_path)
    finally:
        spark.stop()

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Stockfish-backed blunder position rows from Silver games.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--stockfish-path")
    parser.add_argument("--fraction", type=float, default=0.01)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-games", type=int)
    parser.add_argument("--max-plies", type=int, default=80)
    parser.add_argument("--depth", type=int, default=12)
    parser.add_argument("--movetime-ms", type=int)
    parser.add_argument("--blunder-threshold-cp", type=int, default=DEFAULT_BLUNDER_THRESHOLD_CP)
    args = parser.parse_args()
    run(
        args.input,
        args.output,
        stockfish_path=resolve_stockfish_path(args.stockfish_path),
        fraction=args.fraction,
        seed=args.seed,
        max_games=args.max_games,
        max_plies=args.max_plies,
        depth=args.depth,
        movetime_ms=args.movetime_ms,
        blunder_threshold_cp=args.blunder_threshold_cp,
    )

if __name__ == "__main__":
    main()