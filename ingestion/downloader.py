# Downloader for Lichess monthly database dumps
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

LICHESS_STANDARD_URL = "https://database.lichess.org/standard/lichess_db_standard_rated_{month}.pgn.zst"

def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()

def download_dump(month: str, output_dir: Path, *, expected_sha256: str | None = None) -> Path:
    """Download a monthly Lichess standard dump and optionally verify SHA256."""

    import httpx

    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"lichess_db_standard_rated_{month}.pgn.zst"
    url = LICHESS_STANDARD_URL.format(month=month)

    with httpx.stream("GET", url, follow_redirects=True, timeout=None) as response:
        response.raise_for_status()
        with target.open("wb") as fh:
            for chunk in response.iter_bytes():
                fh.write(chunk)

    if expected_sha256:
        actual = sha256_file(target)
        if actual.lower() != expected_sha256.lower():
            raise ValueError(f"checksum mismatch for {target}: expected {expected_sha256}, got {actual}")

    return target

def main() -> None:
    parser = argparse.ArgumentParser(description="Download a Lichess monthly dump.")
    parser.add_argument("--month", required=True, help="Month in YYYY-MM format.")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--sha256")
    args = parser.parse_args()

    path = download_dump(args.month, args.output_dir, expected_sha256=args.sha256)
    print(path)

if __name__ == "__main__":
    main()