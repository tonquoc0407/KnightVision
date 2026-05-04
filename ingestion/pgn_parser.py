# Streaming PGN parser for Lichess `.pgn.zst` dumps

from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import re
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass
from pathlib import Path

from ingestion.schema import RAW_GAME_FIELDS, pyarrow_schema

TAG_RE = re.compile(r'^\[(?P<key>[A-Za-z0-9_]+)\s+"(?P<value>.*)"\]$')
CLOCK_RE = re.compile(r"\[%clk\s+([^\]]+)\]")
RESULT_TOKENS = {"1-0", "0-1", "1/2-1/2", "*"}

@dataclass
class ParserMetrics:
    games_seen: int = 0
    rows_written: int = 0
    missing_game_id: int = 0
    missing_players: int = 0
    missing_result: int = 0
    missing_moves: int = 0
    parse_errors: int = 0

    @property
    def suspicious_rows(self) -> int:
        return (
            self.missing_game_id
            + self.missing_players
            + self.missing_result
            + self.missing_moves
            + self.parse_errors
        )

    def as_dict(self) -> dict[str, int]:
        values = asdict(self)
        values["suspicious_rows"] = self.suspicious_rows
        return values

def update_metrics(metrics: ParserMetrics, row: dict[str, object]) -> None:
    metrics.games_seen += 1
    if not row.get("game_id"):
        metrics.missing_game_id += 1
    if not row.get("white") or not row.get("black"):
        metrics.missing_players += 1
    if not row.get("result"):
        metrics.missing_result += 1
    if not row.get("moves"):
        metrics.missing_moves += 1

def extract_game_id(site: str | None) -> str | None:
    if not site:
        return None
    return site.rstrip("/").rsplit("/", 1)[-1] or None

def parse_pgn_game(text: str, *, batch_id: str, source: str = "batch") -> dict[str, object]:
    """Parse one PGN game block into the raw Bronze row shape."""

    headers: dict[str, str] = {}
    move_lines: list[str] = []

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        match = TAG_RE.match(line)
        if match:
            headers[match.group("key")] = match.group("value")
        else:
            move_lines.append(line)

    moves = " ".join(move_lines).strip()
    for token in RESULT_TOKENS:
        if moves.endswith(f" {token}") or moves == token:
            moves = moves[: -len(token)].strip()
            break

    clock_annotations = " ".join(CLOCK_RE.findall(moves))
    site = headers.get("Site")

    return {
        "game_id": extract_game_id(site),
        "white": headers.get("White"),
        "black": headers.get("Black"),
        "result": headers.get("Result"),
        "white_elo": headers.get("WhiteElo"),
        "black_elo": headers.get("BlackElo"),
        "eco": headers.get("ECO"),
        "opening": headers.get("Opening"),
        "time_control": headers.get("TimeControl"),
        "termination": headers.get("Termination"),
        "utc_date": headers.get("UTCDate") or headers.get("Date"),
        "utc_time": headers.get("UTCTime"),
        "moves": moves,
        "clock_annotations": clock_annotations or None,
        "ingested_at": dt.datetime.now(dt.UTC).replace(tzinfo=None),
        "batch_id": batch_id,
        "source": source,
    }

def split_pgn_games(lines: Iterable[str]) -> Iterator[str]:
    """Yield complete PGN game blocks from an iterable of text lines."""

    buffer: list[str] = []
    seen_tags = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[Event ") and seen_tags and buffer:
            yield "\n".join(buffer).strip()
            buffer = [line]
            seen_tags = True
            continue
        if stripped.startswith("["):
            seen_tags = True
        if stripped or buffer:
            buffer.append(line)

    if buffer:
        game = "\n".join(buffer).strip()
        if game:
            yield game

def iter_pgn_zst(path: Path) -> Iterator[str]:
    """Stream decompressed lines from a Zstandard-compressed PGN file."""

    import zstandard as zstd

    with path.open("rb") as fh:
        reader = zstd.ZstdDecompressor().stream_reader(fh)
        with io.TextIOWrapper(reader, encoding="utf-8", errors="replace") as text:
            for line in text:
                yield line.rstrip("\n")

def iter_raw_games(path: Path, *, batch_id: str, source: str = "batch") -> Iterator[dict[str, object]]:
    lines = iter_pgn_zst(path) if path.suffix == ".zst" else path.read_text().splitlines()
    for game_text in split_pgn_games(lines):
        yield parse_pgn_game(game_text, batch_id=batch_id, source=source)

def iter_raw_games_with_metrics(
    path: Path,
    *,
    batch_id: str,
    source: str = "batch",
    metrics: ParserMetrics,
) -> Iterator[dict[str, object]]:
    lines = iter_pgn_zst(path) if path.suffix == ".zst" else path.read_text().splitlines()
    for game_text in split_pgn_games(lines):
        try:
            row = parse_pgn_game(game_text, batch_id=batch_id, source=source)
        except Exception:
            metrics.games_seen += 1
            metrics.parse_errors += 1
            continue
        update_metrics(metrics, row)
        yield row

def batched(rows: Iterable[dict[str, object]], size: int) -> Iterator[list[dict[str, object]]]:
    batch: list[dict[str, object]] = []
    for row in rows:
        batch.append(row)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch

def write_raw_parquet(
    input_path: Path,
    output_dir: Path,
    *,
    batch_id: str,
    source: str = "batch",
    batch_size: int = 100_000,
    metrics_output: Path | None = None,
) -> ParserMetrics:
    """Parse PGN input and write raw Parquet batches. Returns parse metrics."""

    import pyarrow as pa
    import pyarrow.parquet as pq

    output_dir.mkdir(parents=True, exist_ok=True)
    metrics = ParserMetrics()
    rows_iter = iter_raw_games_with_metrics(input_path, batch_id=batch_id, source=source, metrics=metrics)
    for index, rows in enumerate(batched(rows_iter, batch_size)):
        table = pa.Table.from_pylist(
            [{field: row.get(field) for field in RAW_GAME_FIELDS} for row in rows],
            schema=pyarrow_schema(),
        )
        pq.write_table(table, output_dir / f"part-{index:05d}.parquet", compression="snappy")
        metrics.rows_written += len(rows)
    if metrics_output:
        metrics_output.parent.mkdir(parents=True, exist_ok=True)
        metrics_output.write_text(json.dumps(metrics.as_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return metrics

def main() -> None:
    parser = argparse.ArgumentParser(description="Parse Lichess PGN dumps into raw Parquet.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--source", default="batch")
    parser.add_argument("--batch-size", type=int, default=100_000)
    parser.add_argument("--metrics-output", type=Path, help="Optional JSON path for parser diagnostics.")
    args = parser.parse_args()

    metrics = write_raw_parquet(
        args.input,
        args.output,
        batch_id=args.batch_id,
        source=args.source,
        batch_size=args.batch_size,
        metrics_output=args.metrics_output,
    )
    print(
        "wrote "
        f"{metrics.rows_written} raw games to {args.output}; "
        f"suspicious_rows={metrics.suspicious_rows}"
    )

if __name__ == "__main__":
    main()