import stat

import chess
import pytest

from pipeline.gold.blunder_positions import (
    DEFAULT_BLUNDER_THRESHOLD_CP,
    evaluate_game_positions,
    game_phase_from_ply,
    material_balance_cp,
    resolve_stockfish_path,
    score_loss,
)


def test_evaluate_game_positions_emits_fen_cp_loss_and_blunder_flag():
    scores = [40, -220, 15, 5]

    def evaluator(_board: chess.Board, _pov: chess.Color) -> int:
        return scores.pop(0)

    rows = evaluate_game_positions(
        {
            "game_id": "game-1",
            "moves_uci": ["e2e4", "e7e5"],
            "clock_seconds": [180, 175],
            "time_control_type": "blitz",
            "year": 2024,
            "white_elo": 1500,
            "black_elo": 1510,
        },
        evaluator,
        blunder_threshold_cp=DEFAULT_BLUNDER_THRESHOLD_CP,
    )

    assert len(rows) == 2
    assert rows[0]["game_id"] == "game-1"
    assert rows[0]["ply_number"] == 1
    assert rows[0]["fen"] == chess.STARTING_FEN
    assert rows[0]["move_uci"] == "e2e4"
    assert rows[0]["square"] == "e4"
    assert rows[0]["game_phase"] == "opening"
    assert rows[0]["year"] == 2024
    assert rows[0]["player_elo"] == 1500
    assert rows[0]["time_remaining_seconds"] == 180
    assert rows[0]["cp_loss"] == 260
    assert rows[0]["is_blunder"] is True
    assert rows[1]["player_elo"] == 1510
    assert rows[1]["cp_loss"] == 10
    assert rows[1]["is_blunder"] is False

def test_evaluate_game_positions_stops_at_first_illegal_move():
    def evaluator(_board: chess.Board, _pov: chess.Color) -> int:
        return 0

    rows = evaluate_game_positions(
        {
            "game_id": "game-2",
            "moves_uci": ["e2e4", "e2e5", "g1f3"],
            "clock_seconds": [],
            "time_control_type": "rapid",
            "year": 2024,
            "white_elo": 1600,
            "black_elo": 1600,
        },
        evaluator,
    )

    assert [row["move_uci"] for row in rows] == ["e2e4"]

def test_material_balance_phase_and_score_helpers():
    board = chess.Board()
    board.remove_piece_at(chess.E7)
    assert material_balance_cp(board, chess.WHITE) == 100
    assert material_balance_cp(board, chess.BLACK) == -100
    assert score_loss(50, -25) == 75
    assert score_loss(-25, 50) == 0
    assert game_phase_from_ply(12) == "opening"
    assert game_phase_from_ply(30) == "middlegame"
    assert game_phase_from_ply(80) == "endgame"

def test_resolve_stockfish_path_requires_existing_engine(monkeypatch, tmp_path):
    monkeypatch.delenv("STOCKFISH_PATH", raising=False)
    with pytest.raises(ValueError, match="STOCKFISH_PATH"):
        resolve_stockfish_path(None)

    with pytest.raises(FileNotFoundError, match="Stockfish binary not found"):
        resolve_stockfish_path("/missing/stockfish")

    stockfish = tmp_path / "stockfish"
    stockfish.write_text("#!/bin/sh\n", encoding="utf-8")
    with pytest.raises(PermissionError, match="not executable"):
        resolve_stockfish_path(str(stockfish))

    stockfish.chmod(stockfish.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("STOCKFISH_PATH", str(stockfish))
    assert resolve_stockfish_path(None) == str(stockfish)
    assert resolve_stockfish_path(str(stockfish)) == str(stockfish)