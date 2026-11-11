import pytest

import aifa_rag.embeddings as emb


class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = headers or {}
        self.text = text

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path, monkeypatch):
    """Isola i test da un eventuale `.env` reale con la chiave."""
    monkeypatch.setattr(emb.config, "BASE_DIR", tmp_path)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(emb, "_cooldown_until", 0.0)


def test_embed_texts_batches_and_keeps_order(monkeypatch):
    calls = []

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append(json["input"])
        data = [
            {"index": i, "embedding": [float(len(text)), 0.0]}
            for i, text in reversed(list(enumerate(json["input"])))
        ]
        return FakeResponse(payload={"data": data})

    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    monkeypatch.setattr(emb.httpx, "post", fake_post)

    vectors = emb.embed_texts(["ab", "abc", "abcd"], batch_size=2)

    assert [len(c) for c in calls] == [2, 1]
    assert vectors == [[2.0, 0.0], [3.0, 0.0], [4.0, 0.0]]


def test_embed_texts_sends_model_and_auth(monkeypatch):
    seen = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        seen["url"] = url
        seen["model"] = json["model"]
        seen["auth"] = headers["Authorization"]
        return FakeResponse(payload={"data": [{"index": 0, "embedding": [1.0]}]})

    monkeypatch.setenv("OPENROUTER_API_KEY", "k-123")
    monkeypatch.setattr(emb.httpx, "post", fake_post)

    emb.embed_texts(["x"])

    assert seen["url"] == "https://openrouter.ai/api/v1/embeddings"
    assert seen["model"] == "nvidia/nemotron-3-embed-1b:free"
    assert seen["auth"] == "Bearer k-123"


def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(emb.EmbeddingError, match="OPENROUTER_API_KEY"):
        emb.embed_texts(["x"])


def test_key_can_come_from_dotenv(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text(
        "# commento\nOPENROUTER_API_KEY=\"k-dotenv\"\nALTRA=1\n", encoding="utf-8"
    )

    seen = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        seen["auth"] = headers["Authorization"]
        return FakeResponse(payload={"data": [{"index": 0, "embedding": [1.0]}]})

    monkeypatch.setattr(emb.httpx, "post", fake_post)

    emb.embed_texts(["x"])
    assert seen["auth"] == "Bearer k-dotenv"


def test_server_error_retries_then_raises(monkeypatch):
    attempts = []

    def fake_post(url, json=None, headers=None, timeout=None):
        attempts.append(1)
        return FakeResponse(status_code=503, text="busy")

    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    monkeypatch.setattr(emb.httpx, "post", fake_post)
    monkeypatch.setattr(emb.time, "sleep", lambda *_: None)

    with pytest.raises(emb.EmbeddingError, match="503"):
        emb.embed_texts(["x"])

    assert len(attempts) == emb.RETRIES


def test_client_error_is_not_retried(monkeypatch):
    attempts = []

    def fake_post(url, json=None, headers=None, timeout=None):
        attempts.append(1)
        return FakeResponse(status_code=401, text="no auth")

    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    monkeypatch.setattr(emb.httpx, "post", fake_post)

    with pytest.raises(emb.EmbeddingError, match="401"):
        emb.embed_texts(["x"])

    assert len(attempts) == 1


def test_wrong_length_response_raises(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    monkeypatch.setattr(
        emb.httpx,
        "post",
        lambda *a, **k: FakeResponse(payload={"data": [{"index": 0, "embedding": [1.0]}]}),
    )

    with pytest.raises(emb.EmbeddingError, match="attesi 2"):
        emb.embed_texts(["a", "b"])


def test_429_waits_for_reset_from_error_body(monkeypatch):
    clock = {"now": 1_000_000.0}
    sleeps = []

    def fake_sleep(seconds):
        sleeps.append(seconds)
        clock["now"] += seconds

    monkeypatch.setattr(emb.time, "time", lambda: clock["now"])
    monkeypatch.setattr(emb.time, "sleep", fake_sleep)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")

    reset_ms = int((clock["now"] + 30) * 1000)
    responses = [
        FakeResponse(
            status_code=429,
            text="slow down",
            payload={
                "error": {
                    "metadata": {
                        "headers": {
                            "X-RateLimit-Remaining": "0",
                            "X-RateLimit-Reset": str(reset_ms),
                        }
                    }
                }
            },
        ),
        FakeResponse(payload={"data": [{"index": 0, "embedding": [1.0]}]}),
    ]
    monkeypatch.setattr(emb.httpx, "post", lambda *a, **k: responses.pop(0))

    assert emb.embed_texts(["x"]) == [[1.0]]
    assert sleeps == [31.0]


def test_zero_remaining_throttles_next_batch(monkeypatch):
    clock = {"now": 1_000_000.0}
    sleeps = []

    def fake_sleep(seconds):
        sleeps.append(seconds)
        clock["now"] += seconds

    monkeypatch.setattr(emb.time, "time", lambda: clock["now"])
    monkeypatch.setattr(emb.time, "sleep", fake_sleep)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")

    reset_ms = int((clock["now"] + 20) * 1000)
    responses = [
        FakeResponse(
            payload={"data": [{"index": 0, "embedding": [1.0]}]},
            headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(reset_ms)},
        ),
        FakeResponse(
            payload={"data": [{"index": 0, "embedding": [2.0]}]},
            headers={"X-RateLimit-Remaining": "19"},
        ),
    ]
    monkeypatch.setattr(emb.httpx, "post", lambda *a, **k: responses.pop(0))

    assert emb.embed_texts(["a", "b"], batch_size=1) == [[1.0], [2.0]]
    assert sleeps == [21.0]