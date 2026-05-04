import json

from ingestion.pgn_parser import extract_game_id, parse_pgn_game, split_pgn_games, write_raw_parquet

SAMPLE = """[Event "Rated Blitz game"]
[Site "https://lichess.org/abc123"]
[Date "2024.01.01"]
[UTCDate "2024.01.01"]
[UTCTime "12:00:00"]
[White "alice"]
[Black "bob"]
[Result "1-0"]
[WhiteElo "1500"]
[BlackElo "1450"]
[ECO "B20"]
[Opening "Sicilian Defense"]
[TimeControl "300+0"]
[Termination "Normal"]

1. e4 { [%clk 0:05:00] } c5 2. Nf3 d6 1-0
"""

def test_extract_game_id():
    assert extract_game_id("https://lichess.org/abc123") == "abc123"

def test_parse_pgn_game():
    row = parse_pgn_game(SAMPLE, batch_id="2024-01")
    assert row["game_id"] == "abc123"
    assert row["white"] == "alice"
    assert row["black"] == "bob"
    assert row["result"] == "1-0"
    assert row["white_elo"] == "1500"
    assert row["clock_annotations"] == "0:05:00"
    assert row["batch_id"] == "2024-01"

def test_split_pgn_games():
    games = list(split_pgn_games((SAMPLE + "\n" + SAMPLE.replace("abc123", "def456")).splitlines()))
    assert len(games) == 2

def test_write_raw_parquet_reports_parser_metrics(tmp_path):
    bad = SAMPLE.replace("[Site \"https://lichess.org/abc123\"]\n", "")
    input_path = tmp_path / "sample.pgn"
    output_dir = tmp_path / "landing"
    metrics_path = tmp_path / "quality" / "parser.json"
    input_path.write_text(SAMPLE + "\n" + bad, encoding="utf-8")

    metrics = write_raw_parquet(input_path, output_dir, batch_id="2024-01", batch_size=1, metrics_output=metrics_path)

    assert metrics.games_seen == 2
    assert metrics.rows_written == 2
    assert metrics.missing_game_id == 1
    assert metrics.suspicious_rows == 1
    assert json.loads(metrics_path.read_text(encoding="utf-8"))["missing_game_id"] == 1