from __future__ import annotations

import httpx
import pytest
import respx

from kol_monitor.client import OpenTwitterClient


@pytest.mark.asyncio
@respx.mock
async def test_user_tweets_parses_camelcase_to_snake():
    respx.post("https://ai.6551.io/open/twitter_user_tweets").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "1800000000000000123",
                        "text": "hi",
                        "createdAt": "2026-05-29T10:00:00Z",
                        "userScreenName": "qinbafrank",
                        "userIdStr": "12345",
                        "retweetCount": 1,
                        "favoriteCount": 2,
                        "replyCount": 0,
                        "quoteCount": 0,
                        "viewCount": 100,
                        "isReply": False,
                        "isQuote": False,
                        "media": [],
                        "urls": [],
                        "mentions": [],
                    }
                ]
            },
        )
    )

    client = OpenTwitterClient(token="test", base_url="https://ai.6551.io")
    tweets = await client.user_tweets("qinbafrank", max_results=10)
    await client.close()

    assert len(tweets) == 1
    assert tweets[0]["tweet_id"] == "1800000000000000123"
    assert tweets[0]["favorite_count"] == 2
    assert tweets[0]["screen_name"] == "qinbafrank"
    assert tweets[0]["url"] == "https://x.com/qinbafrank/status/1800000000000000123"


@pytest.mark.asyncio
@respx.mock
async def test_4xx_does_not_retry():
    route = respx.post("https://ai.6551.io/open/twitter_user_info").mock(
        return_value=httpx.Response(401, json={"error": "invalid token"})
    )

    client = OpenTwitterClient(token="bad", base_url="https://ai.6551.io")
    with pytest.raises(httpx.HTTPStatusError):
        await client.user_info("qinbafrank")
    await client.close()

    assert route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_network_error_retries():
    route = respx.post("https://ai.6551.io/open/twitter_user_info").mock(
        side_effect=[
            httpx.ConnectError("boom"),
            httpx.ConnectError("boom"),
            httpx.Response(
                200,
                json={
                    "data": {
                        "userId": "1",
                        "screenName": "qinbafrank",
                        "name": "qb",
                        "followersCount": 100,
                    }
                },
            ),
        ]
    )

    client = OpenTwitterClient(token="test", base_url="https://ai.6551.io", retry_min=0)
    res = await client.user_info("qinbafrank")
    await client.close()

    assert route.call_count == 3
    assert res["screen_name"] == "qinbafrank"
