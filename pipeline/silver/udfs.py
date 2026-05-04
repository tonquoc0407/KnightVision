# Pure helpers and Spark UDF wrappers used by Silver transforms
from __future__ import annotations

import re

import chess

RESULT_MAP = {"1-0": "white_win", "0-1": "black_win", "1/2-1/2": "draw"}
GAME_END_TOKENS = {*RESULT_MAP, "*"}
BOT_SUFFIX_RE = re.compile(r"bot$", re.IGNORECASE)
TIME_CONTROL_TYPES = [
    ("bullet", 0, 179),
    ("blitz", 180, 479),
    ("rapid", 480, 1499),
    ("classical", 1500, 21_600),
]

def normalize_result(result: str | None) -> str | None:
    if result is None:
        return None
    return RESULT_MAP.get(result)

def normalize_termination(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower().replace(" ", "_")
    aliases = {
        "normal": "normal",
        "time_forfeit": "time_forfeit",
        "abandoned": "abandoned",
        "rules_infraction": "rules_infraction",
    }
    return aliases.get(normalized, normalized)

def result_reason(termination: str | None) -> str | None:
    normalized = normalize_termination(termination)
    if normalized is None:
        return None
    if normalized == "normal":
        return "checkmate_or_resignation"
    if normalized == "time_forfeit":
        return "timeout"
    if normalized == "abandoned":
        return "abandoned"
    if normalized == "rules_infraction":
        return "rules_infraction"
    return normalized

def parse_elo(value: str | int | None) -> int | None:
    if value in (None, "", "?"):
        return None
    try:
        elo = int(value)
    except (TypeError, ValueError):
        return None
    return elo if 400 <= elo <= 3500 else None

def parse_time_control(value: str | None) -> dict[str, int | str | None]:
    if not value or value == "-":
        return {"base_seconds": None, "increment_seconds": None, "estimated_total": None, "time_control_type": None}
    if value.lower() == "correspondence":
        return {
            "base_seconds": None,
            "increment_seconds": None,
            "estimated_total": None,
            "time_control_type": "correspondence",
        }
    match = re.match(r"^(?P<base>\d+)\+(?P<inc>\d+)$", value)
    if not match:
        return {"base_seconds": None, "increment_seconds": None, "estimated_total": None, "time_control_type": None}
    base = int(match.group("base"))
    increment = int(match.group("inc"))
    estimated_total = base + 40 * increment
    tc_type = "classical"
    for name, low, high in TIME_CONTROL_TYPES:
        if low <= estimated_total <= high:
            tc_type = name
            break
    return {
        "base_seconds": base,
        "increment_seconds": increment,
        "estimated_total": estimated_total,
        "time_control_type": tc_type,
    }

def parse_clock_value(value: str | None) -> int | None:
    if not value:
        return None
    cleaned = value.strip()
    parts = cleaned.split(":")
    try:
        if len(parts) == 3:
            hours, minutes, seconds = parts
            return int(hours) * 3600 + int(minutes) * 60 + int(float(seconds))
        if len(parts) == 2:
            minutes, seconds = parts
            return int(minutes) * 60 + int(float(seconds))
        if len(parts) == 1:
            return int(float(parts[0]))
    except ValueError:
        return None
    return None

def parse_clock_seconds(clock_annotations: str | None) -> list[int]:
    if not clock_annotations:
        return []
    seconds: list[int] = []
    for value in clock_annotations.split():
        parsed = parse_clock_value(value)
        if parsed is not None:
            seconds.append(parsed)
    return seconds

def time_remaining_bucket(seconds: int | None) -> str | None:
    if seconds is None:
        return None
    if seconds <= 5:
        return "0-5s"
    if seconds <= 15:
        return "6-15s"
    if seconds <= 30:
        return "16-30s"
    if seconds <= 60:
        return "31-60s"
    return "60s+"

def elo_bucket(white_elo: int | None, black_elo: int | None, size: int = 200) -> str | None:
    values = [value for value in (white_elo, black_elo) if value is not None]
    if not values:
        return None
    avg = sum(values) // len(values)
    low = (avg // size) * size
    high = low + size
    return f"{low}-{high}" if high < 2200 else "2200+"

def strip_pgn_noise(moves: str) -> str:
    moves = re.sub(r"\{[^}]*\}", " ", moves)
    moves = re.sub(r";[^\n\r]*", " ", moves)
    while re.search(r"\([^()]*\)", moves):
        moves = re.sub(r"\([^()]*\)", " ", moves)
    moves = re.sub(r"\$\d+", " ", moves)
    moves = re.sub(r"\d+\.(\.\.)?", " ", moves)
    moves = re.sub(r"\s+", " ", moves)
    return moves.strip()

def clean_san_token(token: str) -> str:
    token = token.strip()
    token = token.replace("\u00a0", "")
    token = token.lstrip(".")
    token = token.rstrip("!?")
    token = re.sub(r"^[!?]+", "", token)
    return token

def parse_san_tokens(moves: str | None) -> list[str]:
    """Return cleaned SAN tokens with comments, NAGs, and variations removed."""

    if not moves:
        return []
    tokens = []
    for token in strip_pgn_noise(moves).split():
        token = clean_san_token(token)
        if token in GAME_END_TOKENS:
            continue
        if token:
            tokens.append(token)
    return tokens

def parse_moves(moves: str | None) -> list[str]:
    """Convert SAN PGN movetext to UCI moves using legal board state.

    Invalid or partial movetext returns the legal prefix parsed before the
    first invalid token. This keeps large batch jobs resilient to occasional
    malformed games while still producing real UCI moves for valid PGN.
    """

    board = chess.Board()
    uci_moves: list[str] = []
    for token in parse_san_tokens(moves):
        try:
            move = board.parse_san(token)
        except ValueError:
            break
        uci_moves.append(move.uci())
        board.push(move)
    return uci_moves

def move_feature_summary(moves_uci: list[str] | None) -> dict[str, int | bool]:
    board = chess.Board()
    has_capture = False
    capture_count = 0
    white_castled = False
    black_castled = False
    legal_prefix_length = 0

    for move_uci in moves_uci or []:
        try:
            move = chess.Move.from_uci(move_uci)
        except ValueError:
            break
        if move not in board.legal_moves:
            break
        if board.is_capture(move):
            has_capture = True
            capture_count += 1
        if board.is_castling(move):
            if board.turn == chess.WHITE:
                white_castled = True
            else:
                black_castled = True
        board.push(move)
        legal_prefix_length += 1

    return {
        "has_capture": has_capture,
        "capture_count": capture_count,
        "white_castled": white_castled,
        "black_castled": black_castled,
        "legal_prefix_length": legal_prefix_length,
    }

def has_bot_player(white: str | None, black: str | None) -> bool:
    return any(BOT_SUFFIX_RE.search(player or "") is not None for player in (white, black))

def classify_game_phase(move_number: int | None, piece_count: int | None = None) -> str | None:
    if move_number is None:
        return None
    if piece_count is not None and piece_count <= 20:
        return "endgame"
    if move_number <= 10:
        return "opening"
    if move_number <= 30:
        return "middlegame"
    return "endgame"

def register_udfs(spark):
    from pyspark.sql import functions as F
    from pyspark.sql import types as T

    spark.udf.register("kv_normalize_result", normalize_result, T.StringType())
    spark.udf.register("kv_normalize_termination", normalize_termination, T.StringType())
    spark.udf.register("kv_parse_elo", parse_elo, T.IntegerType())
    spark.udf.register("kv_parse_clock_seconds", parse_clock_seconds, T.ArrayType(T.IntegerType()))
    spark.udf.register("kv_parse_san_tokens", parse_san_tokens, T.ArrayType(T.StringType()))
    spark.udf.register("kv_parse_moves", parse_moves, T.ArrayType(T.StringType()))
    spark.udf.register("kv_classify_game_phase", classify_game_phase, T.StringType())
    spark.udf.register("kv_elo_bucket", elo_bucket, T.StringType())
    spark.udf.register("kv_result_reason", result_reason, T.StringType())
    return F