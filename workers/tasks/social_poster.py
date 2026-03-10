"""
Social poster — called by the Telegram webhook when user approves a draft.

Primary: direct API calls (LinkedIn, Facebook).
Fallback: Make.com webhook.
Fallback: sends text back to Telegram for manual copy-paste.

Required env vars for Facebook:
  FACEBOOK_PAGE_ID          — numeric Facebook Page ID
  FACEBOOK_PAGE_ACCESS_TOKEN — long-lived Page access token (pages_manage_posts scope)

Required env vars for LinkedIn:
  LINKEDIN_ACCESS_TOKEN, LINKEDIN_AUTHOR_URN
"""
import logging
import os

import requests

log = logging.getLogger(__name__)

MAKE_WEBHOOK_URL = os.environ.get("MAKE_WEBHOOK_URL", "")
TWITTER_API_KEY = os.environ.get("TWITTER_API_KEY", "")
TWITTER_API_SECRET = os.environ.get("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN = os.environ.get("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_TOKEN_SECRET = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET", "")
LINKEDIN_ACCESS_TOKEN = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
LINKEDIN_AUTHOR_URN = os.environ.get("LINKEDIN_AUTHOR_URN", "")
FACEBOOK_PAGE_ID = os.environ.get("FACEBOOK_PAGE_ID", "")
FACEBOOK_PAGE_ACCESS_TOKEN = os.environ.get("FACEBOOK_PAGE_ACCESS_TOKEN", "")


def post_via_make(platform: str, text: str, draft: dict) -> str | None:
    """
    Send approved draft to Make.com webhook.
    Make.com scenario handles: LinkedIn company page, Facebook page, Twitter.
    Returns error string or None on success.
    """
    if not MAKE_WEBHOOK_URL:
        return "not configured"
    try:
        payload = {
            "platform": platform,       # "linkedin" | "twitter" | "facebook" | "both"
            "text": text,
            "entity": draft.get("entity", ""),
            "url": draft.get("url", ""),
            "type": draft.get("type", ""),
        }
        r = requests.post(MAKE_WEBHOOK_URL, json=payload, timeout=15)
        if r.status_code in (200, 204):
            log.info("Make.com webhook sent: platform=%s entity=%s", platform, draft.get("entity"))
            return None
        return f"Make.com {r.status_code}: {r.text[:200]}"
    except Exception as e:
        log.warning("Make.com webhook failed: %s", e)
        return str(e)


def post_to_linkedin(text: str) -> str | None:
    """Post directly to LinkedIn company/personal page via API v2."""
    if not LINKEDIN_ACCESS_TOKEN or not LINKEDIN_AUTHOR_URN:
        return "not configured"
    try:
        payload = {
            "author": LINKEDIN_AUTHOR_URN,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
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
            post_id = r.headers.get("x-restli-id", "?")
            log.info("LinkedIn post published: id=%s", post_id)
            return None
        return f"LinkedIn {r.status_code}: {r.text[:200]}"
    except Exception as e:
        log.warning("LinkedIn post failed: %s", e)
        return str(e)


def post_to_facebook(text: str, link: str = "") -> str | None:
    """Post to a Facebook Page via Graph API."""
    if not FACEBOOK_PAGE_ID or not FACEBOOK_PAGE_ACCESS_TOKEN:
        return "not configured"
    try:
        payload: dict = {"message": text, "access_token": FACEBOOK_PAGE_ACCESS_TOKEN}
        if link:
            payload["link"] = link
        r = requests.post(
            f"https://graph.facebook.com/v19.0/{FACEBOOK_PAGE_ID}/feed",
            json=payload,
            timeout=15,
        )
        if r.status_code == 200:
            post_id = r.json().get("id", "?")
            log.info("Facebook post published: id=%s", post_id)
            return None
        return f"Facebook {r.status_code}: {r.text[:200]}"
    except Exception as e:
        log.warning("Facebook post failed: %s", e)
        return str(e)


def post_to_twitter(text: str) -> str | None:
    """Direct Twitter post via tweepy (fallback if not using Make.com)."""
    if not all([TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET]):
        return "not configured"
    try:
        import tweepy
        client = tweepy.Client(
            consumer_key=TWITTER_API_KEY,
            consumer_secret=TWITTER_API_SECRET,
            access_token=TWITTER_ACCESS_TOKEN,
            access_token_secret=TWITTER_ACCESS_TOKEN_SECRET,
        )
        resp = client.create_tweet(text=text[:280])
        log.info("Twitter post published: tweet_id=%s", resp.data["id"])
        return None
    except Exception as e:
        log.warning("Twitter post failed: %s", e)
        return str(e)
