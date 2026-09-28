"""Instagram and Facebook numbers from Meta's Graph API.

Instagram uses Business Discovery: an Instagram business account the token can use looks up any
other business or creator account by username, so clients (and prospects) don't need to grant
anything. Facebook Pages need Volstro to have access to the Page, for example as a partner in
the client's Meta Business Settings.
"""

from datetime import datetime, timedelta
from statistics import mean

import httpx

from .config import GRAPH_URL, RECENT_POSTS


class MetaError(Exception):
    pass


async def _get(client: httpx.AsyncClient, path: str, token: str, **params) -> dict:
    try:
        resp = await client.get(f"{GRAPH_URL}/{path}", params={**params, "access_token": token})
        data = resp.json()
    except (httpx.HTTPError, ValueError) as e:
        # Never surface the request URL: it contains the access token.
        raise MetaError(f"couldn't reach Meta ({type(e).__name__})") from None
    if resp.status_code != 200 or "error" in data:
        raise MetaError((data.get("error") or {}).get("message") or f"HTTP {resp.status_code}")
    return data


async def check(client, token: str) -> dict:
    """The Facebook Pages the token can see and the first linked Instagram business account."""
    data = await _get(client, "me/accounts", token, fields="name,instagram_business_account{id,username}", limit=100)
    pages = data.get("data", [])
    instagram = next((p["instagram_business_account"] for p in pages if p.get("instagram_business_account")), None)
    return {"pages": [p.get("name", "") for p in pages], "instagram": instagram}


async def instagram(client, token: str, ig_user_id: str, username: str, now: datetime) -> dict:
    fields = (f"business_discovery.username({username})"
              f"{{followers_count,media.limit({RECENT_POSTS}){{timestamp,like_count,comments_count}}}}")
    found = (await _get(client, ig_user_id, token, fields=fields)).get("business_discovery")
    if not found:
        raise MetaError("Instagram found no business or creator account with this username")
    posts = [(datetime.fromisoformat(m["timestamp"]), m.get("like_count"), m.get("comments_count"))
             for m in found.get("media", {}).get("data", [])]
    return numbers(found["followers_count"], posts, now)


async def facebook(client, token: str, page: str, now: datetime) -> dict:
    try:
        page_token = (await _get(client, page, token, fields="access_token")).get("access_token") or token
    except MetaError:
        page_token = token  # not a Page this token manages; the next call says what's wrong
    fields = (f"followers_count,posts.limit({RECENT_POSTS})"
              "{created_time,reactions.summary(total_count).limit(0),comments.summary(total_count).limit(0)}")
    data = await _get(client, page, page_token, fields=fields)
    if data.get("followers_count") is None:
        raise MetaError("Meta returned no follower count for this Page")
    total = lambda post, edge: post.get(edge, {}).get("summary", {}).get("total_count")
    posts = [(datetime.fromisoformat(p["created_time"]), total(p, "reactions"), total(p, "comments"))
             for p in data.get("posts", {}).get("data", [])]
    return numbers(data["followers_count"], posts, now)


def numbers(followers: int, posts: list[tuple], now: datetime) -> dict:
    """A day's snapshot from the follower count and recent posts [(time, likes, comments)]."""
    settled = [p for p in posts if now - p[0] >= timedelta(days=1)]  # newer posts are still collecting likes
    likes = [p[1] for p in settled if p[1] is not None]  # like counts can be hidden
    comments = [p[2] for p in settled if p[2] is not None]
    return {
        "followers": int(followers),
        "posts_7d": sum(now - p[0] < timedelta(days=7) for p in posts),
        "avg_likes": round(mean(likes), 1) if likes else None,
        "avg_comments": round(mean(comments), 1) if comments else None,
        "last_post": max(p[0] for p in posts).astimezone().date().isoformat() if posts else None,
    }
