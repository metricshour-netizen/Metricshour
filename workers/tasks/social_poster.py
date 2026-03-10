"""
Social poster — called by the Telegram webhook when user approves a draft.
Handles Twitter (X) and LinkedIn posting.

Required env vars (add when ready):
  TWITTER_API_KEY, TWITTER_API_SECRET
  TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET
  LINKEDIN_ACCESS_TOKEN, LINKEDIN_AUTHOR_URN  (urn:li:person:xxx or urn:li:organization:xxx)
"""
import json
import logging
import os

log = logging.getLogger(__name__)

TWITTER_API_KEY = os.environ.get("TWITTER_API_KEY", "")
TWITTER_API_SECRET = os.environ.get("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN = os.environ.get("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_TOKEN_SECRET = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET", "")

LINKEDIN_ACCESS_TOKEN = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
LINKEDIN_AUTHOR_URN = os.environ.get("LINKEDIN_AUTHOR_URN", "")  # urn:li:person:xxx


def post_to_twitter(text: str) -> str | None:
    """Post to Twitter/X via API v2. Returns error string or None on success."""
    if not all([TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET]):
        return "Twitter API keys not configured (add TWITTER_API_KEY/SECRET/ACCESS_TOKEN/ACCESS_TOKEN_SECRET to .env)"
    try:
        import tweepy
        client = tweepy.Client(
            consumer_key=TWITTER_API_KEY,
            consumer_secret=TWITTER_API_SECRET,
            access_token=TWITTER_ACCESS_TOKEN,
            access_token_secret=TWITTER_ACCESS_TOKEN_SECRET,
        )
        resp = client.create_tweet(text=text[:280])
        tweet_id = resp.data["id"]
        log.info("Twitter post published: tweet_id=%s", tweet_id)
        return None
    except Exception as e:
        log.warning("Twitter post failed: %s", e)
        return str(e)


def post_to_linkedin(text: str) -> str | None:
    """Post to LinkedIn via UGC Posts API. Returns error string or None on success."""
    if not LINKEDIN_ACCESS_TOKEN or not LINKEDIN_AUTHOR_URN:
        return "LinkedIn not configured (add LINKEDIN_ACCESS_TOKEN + LINKEDIN_AUTHOR_URN to .env)"
    try:
        import requests
        payload = {
            "author": LINKEDIN_AUTHOR_URN,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text[:3000]},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            },
        }
        r = requests.post(
            "https://api.linkedin.com/v2/ugcPosts",
            headers={
                "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
                "Content-Type": "application/json",
                "X-Restli-Protocol-Version": "2.0.0",
            },
            json=payload,
            timeout=15,
        )
        if r.status_code in (200, 201):
            log.info("LinkedIn post published: %s", r.headers.get("x-restli-id", ""))
            return None
        return f"LinkedIn {r.status_code}: {r.text[:200]}"
    except Exception as e:
        log.warning("LinkedIn post failed: %s", e)
        return str(e)
