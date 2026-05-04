# Optional Lichess API to Kafka producer.

# The project does not require Kafka for the core batch pipeline. This module is
# kept dependency-light: it can stream Lichess NDJSON to stdout for smoke tests,
# and only imports kafka-python when `--bootstrap-servers` is used.

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from typing import Protocol

import httpx

LICHESS_API = "https://lichess.org"
USER_AGENT = "KnightVision-Lichess-Producer/1.0"

class Producer(Protocol):
    def send(self, topic: str, value: bytes, key: bytes | None = None) -> None: ...

    def flush(self) -> None: ...

@dataclass(frozen=True)
class ProducerConfig:
    topic: str
    source: str = "lichess_api"
    max_events: int | None = None

class StdoutProducer:
    # Producer implementation used for local smoke tests and demos

    def __init__(self, stream=None) -> None:
        self.stream = stream or sys.stdout.buffer

    def send(self, topic: str, value: bytes, key: bytes | None = None) -> None:
        envelope = {
            "topic": topic,
            "key": key.decode("utf-8") if key else None,
            "value": json.loads(value.decode("utf-8")),
        }
        self.stream.write(json.dumps(envelope, sort_keys=True).encode("utf-8") + b"\n")

    def flush(self) -> None:
        if hasattr(self.stream, "flush"):
            self.stream.flush()

class KafkaProducerAdapter:
    """Thin adapter around kafka-python, imported lazily because Kafka is optional."""

    def __init__(self, bootstrap_servers: str) -> None:
        try:
            from kafka import KafkaProducer
        except ImportError as exc:
            raise RuntimeError(
                "Kafka publishing requires kafka-python. Install it separately or omit --bootstrap-servers "
                "to use stdout mode."
            ) from exc

        self._producer = KafkaProducer(bootstrap_servers=bootstrap_servers)

    def send(self, topic: str, value: bytes, key: bytes | None = None) -> None:
        self._producer.send(topic, key=key, value=value)

    def flush(self) -> None:
        self._producer.flush()

def auth_headers(token: str | None = None) -> dict[str, str]:
    headers = {"Accept": "application/x-ndjson", "User-Agent": USER_AGENT}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers

def stream_url(*, user: str | None = None, users: Iterable[str] | None = None, max_games: int | None = None) -> str:
    if user:
        url = f"{LICHESS_API}/api/games/user/{user}?pgnInJson=true&clocks=true&opening=true"
        if max_games:
            url = f"{url}&max={max_games}"
        return url

    user_list = ",".join(users or [])
    if not user_list:
        raise ValueError("either user or users must be provided")
    return f"{LICHESS_API}/api/stream/games-by-users?users={user_list}&clocks=true&opening=true"

def iter_lichess_events(client: httpx.Client, url: str, *, headers: Mapping[str, str]) -> Iterator[dict[str, object]]:
    with client.stream("GET", url, headers=dict(headers), timeout=None) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if not line:
                continue
            yield json.loads(line)

def event_key(event: Mapping[str, object]) -> bytes | None:
    game_id = event.get("id") or event.get("game_id")
    return str(game_id).encode("utf-8") if game_id else None

def encode_event(event: Mapping[str, object], *, source: str) -> bytes:
    payload = {
        "source": source,
        "ingested_at": dt.datetime.now(dt.UTC).isoformat(),
        "event": event,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def publish_events(events: Iterable[Mapping[str, object]], producer: Producer, config: ProducerConfig) -> int:
    count = 0
    for event in events:
        producer.send(config.topic, value=encode_event(event, source=config.source), key=event_key(event))
        count += 1
        if config.max_events and count >= config.max_events:
            break
    producer.flush()
    return count

def main() -> None:
    parser = argparse.ArgumentParser(description="Stream Lichess API game events to Kafka or stdout.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--user", help="Single Lichess username for /api/games/user/{username}.")
    source.add_argument("--users", help="Comma-separated usernames for /api/stream/games-by-users.")
    parser.add_argument("--topic", default="knightvision.lichess.games")
    parser.add_argument("--bootstrap-servers", help="Kafka bootstrap servers. Omit to write JSON envelopes to stdout.")
    parser.add_argument("--token", help="Optional Lichess API token.")
    parser.add_argument("--max-events", type=int, help="Stop after publishing this many events.")
    args = parser.parse_args()

    users = [item.strip() for item in args.users.split(",") if item.strip()] if args.users else None
    url = stream_url(user=args.user, users=users, max_games=args.max_events)
    producer: Producer = KafkaProducerAdapter(args.bootstrap_servers) if args.bootstrap_servers else StdoutProducer()

    with httpx.Client() as client:
        events = iter_lichess_events(client, url, headers=auth_headers(args.token))
        count = publish_events(events, producer, ProducerConfig(topic=args.topic, max_events=args.max_events))
    print(f"published {count} Lichess events", file=sys.stderr)

if __name__ == "__main__":
    main()