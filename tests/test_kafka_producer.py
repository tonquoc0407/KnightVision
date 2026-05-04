import io
import json

import pytest

from ingestion.kafka_producer import (
    ProducerConfig,
    StdoutProducer,
    auth_headers,
    encode_event,
    event_key,
    publish_events,
    stream_url,
)


def test_stream_url_for_user_includes_export_options():
    url = stream_url(user="alice", max_games=10)

    assert url.startswith("https://lichess.org/api/games/user/alice?")
    assert "pgnInJson=true" in url
    assert "clocks=true" in url
    assert "opening=true" in url
    assert "max=10" in url

def test_stream_url_for_users_stream():
    assert stream_url(users=["alice", "bob"]) == (
        "https://lichess.org/api/stream/games-by-users?users=alice,bob&clocks=true&opening=true"
    )

def test_stream_url_requires_source():
    with pytest.raises(ValueError, match="either user or users"):
        stream_url()

def test_auth_headers_adds_bearer_token():
    headers = auth_headers("secret")

    assert headers["Accept"] == "application/x-ndjson"
    assert headers["Authorization"] == "Bearer secret"

def test_event_key_prefers_lichess_id():
    assert event_key({"id": "abc123"}) == b"abc123"
    assert event_key({"game_id": "def456"}) == b"def456"
    assert event_key({"white": "alice"}) is None

def test_encode_event_wraps_payload():
    encoded = encode_event({"id": "abc123", "winner": "white"}, source="test")
    payload = json.loads(encoded.decode("utf-8"))

    assert payload["source"] == "test"
    assert payload["event"]["id"] == "abc123"
    assert payload["ingested_at"]

def test_publish_events_respects_max_events_and_stdout_envelope():
    stream = io.BytesIO()
    producer = StdoutProducer(stream)
    events = [{"id": "g1"}, {"id": "g2"}, {"id": "g3"}]

    count = publish_events(events, producer, ProducerConfig(topic="games", source="test", max_events=2))

    assert count == 2
    lines = stream.getvalue().decode("utf-8").splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["topic"] == "games"
    assert first["key"] == "g1"
    assert first["value"]["event"]["id"] == "g1"