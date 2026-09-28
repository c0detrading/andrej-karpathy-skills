import asyncio
from datetime import datetime, timezone

import httpx
import pytest

from pipeline import meta

NOW = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)


def run(handler, coro_fn):
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await coro_fn(client)
    return asyncio.run(go())


def test_instagram_business_discovery():
    seen = {}

    def handler(request):
        seen["path"], seen["fields"] = request.url.path, request.url.params["fields"]
        media = [
            {"timestamp": "2026-09-28T09:00:00+0000", "like_count": 5, "comments_count": 0},    # 3h old: skipped
            {"timestamp": "2026-09-26T09:00:00+0000", "like_count": 120, "comments_count": 10},
            {"timestamp": "2026-09-18T09:00:00+0000", "comments_count": 4},                     # likes hidden
            {"timestamp": "2026-09-10T09:00:00+0000", "like_count": 80, "comments_count": 6},
        ]
        return httpx.Response(200, json={"business_discovery": {"followers_count": 5400, "media": {"data": media}}})

    nums = run(handler, lambda c: meta.instagram(c, "tok", "178", "acme.studio", NOW))
    assert seen["path"] == "/v26.0/178" and "business_discovery.username(acme.studio)" in seen["fields"]
    assert nums == {"followers": 5400, "posts_7d": 2, "avg_likes": 100.0, "avg_comments": 6.7,
                    "last_post": nums["last_post"]}
    assert nums["last_post"] in ("2026-09-28", "2026-09-29")  # local date of the newest post


def test_facebook_page_uses_page_token():
    tokens = []

    def handler(request):
        tokens.append(request.url.params["access_token"])
        if request.url.params["fields"] == "access_token":
            return httpx.Response(200, json={"access_token": "page-tok", "id": "1"})
        posts = [{"created_time": "2026-09-25T10:00:00+0000",
                  "reactions": {"data": [], "summary": {"total_count": 40}},
                  "comments": {"data": [], "summary": {"total_count": 2}}}]
        return httpx.Response(200, json={"followers_count": 2100, "posts": {"data": posts}})

    nums = run(handler, lambda c: meta.facebook(c, "user-tok", "acmestudio", NOW))
    assert tokens == ["user-tok", "page-tok"]
    assert nums["followers"] == 2100 and nums["avg_likes"] == 40 and nums["avg_comments"] == 2 and nums["posts_7d"] == 1


def test_errors_carry_metas_message_not_the_token():
    def handler(request):
        return httpx.Response(400, json={"error": {"message": "Invalid OAuth access token.", "code": 190}})

    with pytest.raises(meta.MetaError, match="Invalid OAuth access token") as e:
        run(handler, lambda c: meta.instagram(c, "secret-token", "178", "acme", NOW))
    assert "secret-token" not in str(e.value)

    def down(request):
        raise httpx.ConnectError(f"failed for {request.url}")

    with pytest.raises(meta.MetaError) as e:
        run(down, lambda c: meta.facebook(c, "secret-token", "acme", NOW))
    assert "secret-token" not in str(e.value)


def test_check_finds_linked_instagram_account():
    def handler(request):
        return httpx.Response(200, json={"data": [
            {"name": "Client Page", "id": "1"},
            {"name": "Volstro Design", "id": "2", "instagram_business_account": {"id": "178", "username": "volstro"}},
        ]})

    found = run(handler, lambda c: meta.check(c, "tok"))
    assert found == {"pages": ["Client Page", "Volstro Design"], "instagram": {"id": "178", "username": "volstro"}}
