import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest

from station import llm, telegram


class FakeMessages:
    def __init__(self, payload, stop_reason="end_turn"):
        self.payload, self.stop_reason, self.kwargs = payload, stop_reason, None

    async def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(stop_reason=self.stop_reason,
                               content=[SimpleNamespace(type="text", text=json.dumps(self.payload))])


def fake_client(monkeypatch, messages):
    monkeypatch.setitem(llm._clients, "k", SimpleNamespace(beta=SimpleNamespace(messages=messages)))


def item(id_, title):
    return {"id": id_, "source": "FinancialJuice", "title": title, "summary": "", "impact": {"tags": []}}


def test_claude_scores_are_clamped_and_tagged(monkeypatch):
    msgs = FakeMessages({"items": [{"id": "a", "GOLD": 7, "NASDAQ": -1.3, "BITCOIN": 0, "reason": "hawkish Fed"}]})
    fake_client(monkeypatch, msgs)
    out = asyncio.run(llm.score("k", [item("a", "Fed hikes")]))
    assert out == {"a": {"GOLD": 3.0, "NASDAQ": -1.5, "BITCOIN": 0.0, "tags": ["AI: hawkish Fed"]}}
    assert msgs.kwargs["output_config"]["format"]["type"] == "json_schema"
    assert msgs.kwargs["fallbacks"] == "default"


def test_claude_refusal_scores_nothing(monkeypatch):
    fake_client(monkeypatch, FakeMessages({}, stop_reason="refusal"))
    assert asyncio.run(llm.score("k", [item("a", "x")])) == {}


def test_telegram_error_hides_token():
    transport = httpx.MockTransport(lambda r: httpx.Response(401, json={"description": "Unauthorized"}))

    async def run():
        async with httpx.AsyncClient(transport=transport) as c:
            await telegram.send(c, "SECRET123", "42", "hi")

    with pytest.raises(telegram.TelegramError) as e:
        asyncio.run(run())
    assert "SECRET123" not in str(e.value) and "Unauthorized" in str(e.value)
