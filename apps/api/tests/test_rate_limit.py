from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from api.config import Settings
from api.graph.build import ChatAgent
from api.main import create_app
from api.providers.base import ProviderRateLimited
from api.providers.fake import HashingEmbedder
from api.rate_limit import SlidingWindow


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_sliding_window_allows_the_limit_then_reports_the_wait():
    clock = FakeClock()
    window = SlidingWindow(limit=2, window=60, clock=clock)
    for _ in range(2):
        assert window.retry_after("a") is None
        window.hit("a")

    assert window.retry_after("a") == 60
    clock.now += 45
    assert window.retry_after("a") == 15
    assert window.retry_after("b") is None  # other visitors are counted separately

    clock.now += 15
    assert window.retry_after("a") is None  # the oldest hit has left the window


def test_zero_means_no_limit():
    window = SlidingWindow(limit=0, window=60)
    for _ in range(100):
        window.hit("a")
    assert window.retry_after("a") is None


def limited_client(**limits) -> TestClient:
    off = {
        "chat_per_client_per_minute": 0,
        "chat_per_client_per_day": 0,
        "chat_per_minute": 0,
        "uploads_per_client_per_hour": 0,
        "browse_per_client_per_minute": 0,
    }
    return TestClient(create_app(Settings(**{**off, **limits}, _env_file=None)))


def ask(client: TestClient, ip: str):
    return client.post(
        "/chat",
        json={"question": "How many orders?", "fileIds": [], "history": []},
        headers={"X-Forwarded-For": f"{ip}, 10.0.0.1"},
    )


def test_each_visitor_has_a_per_minute_limit():
    client = limited_client(chat_per_client_per_minute=2)
    assert [ask(client, "1.1.1.1").status_code for _ in range(2)] == [200, 200]

    blocked = ask(client, "1.1.1.1")
    assert blocked.status_code == 429
    assert 1 <= int(blocked.headers["Retry-After"]) <= 60
    assert blocked.json()["detail"].startswith("You're asking faster than this free demo allows.")

    assert ask(client, "2.2.2.2").status_code == 200  # someone else is not affected


def test_app_wide_limit_protects_the_shared_quota():
    client = limited_client(chat_per_minute=3)
    assert [ask(client, f"9.9.9.{n}").status_code for n in range(3)] == [200, 200, 200]
    blocked = ask(client, "9.9.9.200")
    assert blocked.status_code == 429
    assert blocked.json()["detail"].startswith("The demo is busy right now")


def test_daily_limit_message():
    client = limited_client(chat_per_client_per_day=1)
    ask(client, "1.1.1.1")
    detail = ask(client, "1.1.1.1").json()["detail"]
    assert detail.startswith("You've reached today's question limit") and "hours" in detail


def test_blocked_requests_do_not_use_up_other_limits():
    client = limited_client(chat_per_client_per_minute=1, chat_per_minute=2)
    ask(client, "1.1.1.1")
    for _ in range(5):
        assert ask(client, "1.1.1.1").status_code == 429  # blocked per visitor…
    assert ask(client, "2.2.2.2").status_code == 200  # …without filling the shared quota


def test_upload_limit():
    client = limited_client(uploads_per_client_per_hour=1)
    files = {"file": ("a.txt", b"Some notes about deliveries.")}
    assert client.post("/documents", files=files).status_code == 201
    blocked = client.post("/documents", files=files)
    assert blocked.status_code == 429
    assert blocked.json()["detail"].startswith("Upload limit reached")


class QuotaUsedUp:
    def generate(self, system: str, prompt: str) -> str:
        raise ProviderRateLimited(retry_after=42)


def test_provider_quota_error_tells_the_user_how_long_to_wait(settings):
    app = create_app(settings)
    services = app.state.services
    agent = ChatAgent(settings, HashingEmbedder(), QuotaUsedUp(), services.store, services.sales_db)
    app.state.services = replace(services, agent=agent)

    response = TestClient(app).post("/chat", json={"question": "Hi", "fileIds": [], "history": []})
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "42"
    assert (
        response.json()["detail"]
        == "The free AI quota is used up for the moment. Try again in about 42 seconds."
    )


@pytest.mark.parametrize(
    ("message", "seconds"), [("Please retry in 41.67s.", 42), ("retry in 3s", 3), ("no hint", None)]
)
def test_gemini_retry_delay_is_read_from_the_error(message, seconds):
    from api.providers.gemini import rate_limited

    assert rate_limited(Exception(message)).retry_after == seconds
