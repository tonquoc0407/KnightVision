from pipeline.silver.udfs import (
    classify_game_phase,
    elo_bucket,
    has_bot_player,
    move_feature_summary,
    normalize_result,
    parse_clock_seconds,
    parse_clock_value,
    parse_elo,
    parse_moves,
    parse_san_tokens,
    parse_time_control,
    result_reason,
    time_remaining_bucket,
)


def test_parse_time_control_classifies_speed():
    parsed = parse_time_control("300+0")
    assert parsed["base_seconds"] == 300
    assert parsed["increment_seconds"] == 0
    assert parsed["time_control_type"] == "blitz"

def test_parse_elo_handles_unknowns_and_bounds():
    assert parse_elo("?") is None
    assert parse_elo("1500") == 1500
    assert parse_elo("399") is None

def test_normalize_result():
    assert normalize_result("1-0") == "white_win"
    assert normalize_result("0-1") == "black_win"
    assert normalize_result("1/2-1/2") == "draw"

def test_parse_san_tokens_strips_comments_and_move_numbers():
    assert parse_san_tokens("1. e4 {comment} e5 2. Nf3 Nc6 1-0") == ["e4", "e5", "Nf3", "Nc6"]

def test_parse_moves_converts_san_to_uci():
    assert parse_moves("1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 1-0") == [
        "e2e4",
        "e7e5",
        "g1f3",
        "b8c6",
        "f1b5",
        "a7a6",
    ]

def test_parse_moves_handles_castling_captures_annotations_and_variations():
    moves = "1. e4 e5 2. Nf3 Nc6 (2... d6) 3. Bb5 a6 4. Bxc6?! dxc6 5. O-O *"
    assert parse_moves(moves) == [
        "e2e4",
        "e7e5",
        "g1f3",
        "b8c6",
        "f1b5",
        "a7a6",
        "b5c6",
        "d7c6",
        "e1g1",
    ]

def test_parse_moves_handles_promotion():
    moves = "1. a4 h5 2. a5 h4 3. a6 h3 4. axb7 hxg2 5. bxa8=Q gxh1=Q *"
    assert parse_moves(moves) == [
        "a2a4",
        "h7h5",
        "a4a5",
        "h5h4",
        "a5a6",
        "h4h3",
        "a6b7",
        "h3g2",
        "b7a8q",
        "g2h1q",
    ]

def test_classify_game_phase_and_bucket():
    assert classify_game_phase(5, 32) == "opening"
    assert classify_game_phase(20, 28) == "middlegame"
    assert classify_game_phase(12, 18) == "endgame"
    assert elo_bucket(1500, 1610) == "1400-1600"

def test_parse_clock_seconds_and_buckets():
    assert parse_clock_value("0:05:00") == 300
    assert parse_clock_value("05:03") == 303
    assert parse_clock_seconds("0:00:05 0:00:16 1:02:03") == [5, 16, 3723]
    assert time_remaining_bucket(5) == "0-5s"
    assert time_remaining_bucket(16) == "16-30s"
    assert time_remaining_bucket(61) == "60s+"

def test_move_feature_summary_detects_captures_and_castling():
    features = move_feature_summary(["e2e4", "e7e5", "g1f3", "b8c6", "f1b5", "a7a6", "b5c6", "d7c6", "e1g1"])
    assert features["has_capture"] is True
    assert features["capture_count"] == 2
    assert features["white_castled"] is True
    assert features["black_castled"] is False
    assert features["legal_prefix_length"] == 9

def test_result_reason_and_bot_detection():
    assert result_reason("Time forfeit") == "timeout"
    assert result_reason("Normal") == "checkmate_or_resignation"
    assert has_bot_player("stockfishBOT", "human") is True
    assert has_bot_player("alice", "bob") is False