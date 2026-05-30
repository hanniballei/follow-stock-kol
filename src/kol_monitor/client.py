from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential


class OpenTwitterClient:
    def __init__(
        self,
        token: str,
        base_url: str = "https://ai.6551.io",
        timeout: float = 30,
        retry_attempts: int = 3,
        retry_min: float = 1,
    ) -> None:
        self.retry_attempts = retry_attempts
        self.retry_min = retry_min
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _post(self, path: str, payload: dict[str, Any]) -> Any:
        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type((httpx.ConnectError, httpx.ReadTimeout)),
            stop=stop_after_attempt(self.retry_attempts),
            wait=wait_exponential(min=self.retry_min, max=10),
            reraise=True,
        ):
            with attempt:
                response = await self._client.post(path, json=payload)
                response.raise_for_status()
                body = response.json()
                return body.get("data")
        raise RuntimeError("unreachable retry state")

    async def user_info(self, username: str) -> dict[str, Any] | None:
        data = await self._post("/open/twitter_user_info", {"username": username})
        if not data:
            return None
        return {
            "twitter_user_id": str(data.get("userId") or data.get("userIdStr") or data.get("id") or ""),
            "screen_name": data.get("screenName") or data.get("userScreenName") or username,
            "display_name": data.get("name") or data.get("displayName"),
            "followers_count": data.get("followersCount"),
            "raw": data,
        }

    async def user_tweets(
        self,
        username: str,
        max_results: int = 50,
        product: str = "Latest",
        include_replies: bool = False,
        include_retweets: bool = True,
    ) -> list[dict[str, Any]]:
        data = await self._post(
            "/open/twitter_user_tweets",
            {
                "username": username,
                "maxResults": max_results,
                "product": product,
                "includeReplies": include_replies,
                "includeRetweets": include_retweets,
            },
        )
        return [normalize_tweet(item) for item in (data or [])]

    async def search(
        self,
        from_user: str | None = None,
        since_date: str | None = None,
        until_date: str | None = None,
        keywords: str | list[str] | None = None,
        max_results: int = 100,
        product: str = "Latest",
    ) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {"maxResults": max_results, "product": product}
        if from_user:
            payload["fromUser"] = from_user
        if since_date:
            payload["sinceDate"] = since_date
        if until_date:
            payload["untilDate"] = until_date
        if keywords:
            payload["keywords"] = keywords
        data = await self._post("/open/twitter_search", payload)
        return [normalize_tweet(item) for item in (data or [])]

    async def tweet_by_id(self, tw_id: str) -> dict[str, Any] | None:
        data = await self._post("/open/twitter_tweet_by_id", {"tweetId": str(tw_id)})
        if not data:
            return None
        return normalize_tweet(data)


def normalize_tweet(raw: dict[str, Any]) -> dict[str, Any]:
    tweet_id = str(raw.get("tweet_id") or raw.get("id") or raw.get("idStr") or "")
    screen_name = raw.get("screen_name") or raw.get("userScreenName") or raw.get("user_screen_name")
    created_at = raw.get("created_at") or raw.get("createdAt")
    if isinstance(created_at, datetime):
        created_at = created_at.isoformat()
    media = [
        {
            "type": item.get("type"),
            "orig_url": item.get("orig_url") or item.get("url"),
            "thumb_url": item.get("thumb_url") or item.get("thumbUrl"),
            "url": item.get("url") or item.get("orig_url"),
            "thumbUrl": item.get("thumbUrl") or item.get("thumb_url"),
        }
        for item in (raw.get("media") or [])
    ]
    return {
        "tweet_id": tweet_id,
        "id": tweet_id,
        "text": raw.get("text") or raw.get("full_text") or "",
        "created_at": created_at,
        "createdAt": created_at,
        "language": raw.get("language") or raw.get("lang"),
        "screen_name": screen_name,
        "userScreenName": screen_name,
        "twitter_user_id": str(raw.get("twitter_user_id") or raw.get("userIdStr") or raw.get("userId") or ""),
        "retweet_count": raw.get("retweet_count") or raw.get("retweetCount") or 0,
        "favorite_count": raw.get("favorite_count") or raw.get("favoriteCount") or 0,
        "reply_count": raw.get("reply_count") or raw.get("replyCount") or 0,
        "quote_count": raw.get("quote_count") or raw.get("quoteCount") or 0,
        "view_count": raw.get("view_count") or raw.get("viewCount") or 0,
        "is_reply": bool(raw.get("is_reply") or raw.get("isReply")),
        "is_quote": bool(raw.get("is_quote") or raw.get("isQuote")),
        "is_retweet": bool(raw.get("is_retweet") or raw.get("isRetweet")),
        "conversation_id": raw.get("conversation_id") or raw.get("conversationId"),
        "media": media,
        "urls": raw.get("urls") or [],
        "mentions": raw.get("mentions") or [],
        "url": raw.get("url") or (f"https://x.com/{screen_name}/status/{tweet_id}" if screen_name else None),
        "raw": raw,
    }
