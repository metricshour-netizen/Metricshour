"""
Social poster — called by the Telegram webhook when user approves a draft.

Primary: direct API calls (LinkedIn, Facebook, Instagram, Twitter).
Fallback: Make.com webhook.
Fallback: sends text back to Telegram for manual copy-paste.

Required env vars for Facebook:
  FACEBOOK_PAGE_ID          — numeric Facebook Page ID
  FACEBOOK_PAGE_ACCESS_TOKEN — long-lived Page access token (pages_manage_posts scope)

Required env vars for Instagram:
  INSTAGRAM_BUSINESS_ACCOUNT_ID — Instagram Business Account ID linked to the Facebook Page
  FACEBOOK_PAGE_ACCESS_TOKEN    — same token as above (pages_manage_posts + instagram_basic + instagram_content_publish)

Required env vars for LinkedIn:
  LINKEDIN_ACCESS_TOKEN, LINKEDIN_AUTHOR_URN

Required env vars for Twitter:
  TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET
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
INSTAGRAM_BUSINESS_ACCOUNT_ID = os.environ.get("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")


def post_via_make(
    platform: str,
    text: str,
    draft: dict,
    instagram_caption: str = "",
    image_url: str = "",
) -> str | None:
    """
    Send approved draft to Make.com webhook.
    Make.com scenario handles: LinkedIn company page, Facebook page, Twitter, Instagram.
    Returns error string or None on success.
    """
    if not MAKE_WEBHOOK_URL:
        return "not configured"
    try:
        payload = {
            "platform": platform,       # "linkedin" | "twitter" | "facebook" | "instagram" | "all"
            "text": text,
            "entity": draft.get("entity", ""),
            "url": draft.get("url", ""),
            "type": draft.get("type", ""),
        }
        if instagram_caption:
            payload["instagram_caption"] = instagram_caption
        if image_url:
            payload["image_url"] = image_url
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


def post_to_instagram(caption: str, image_url: str) -> str | None:
    """
    Post a photo to Instagram Business Account via Graph API.

    Step 1: Create a media container (image_url must be a publicly accessible URL).
    Step 2: Publish the container.

    Returns None on success, error string on failure.
    """
    if not INSTAGRAM_BUSINESS_ACCOUNT_ID or not FACEBOOK_PAGE_ACCESS_TOKEN:
        return "not configured"
    if not image_url:
        return "image_url required for Instagram"
    try:
        # Step 1: create media container
        create_resp = requests.post(
            f"https://graph.facebook.com/v19.0/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/media",
            params={
                "image_url": image_url,
                "caption": caption,
                "access_token": FACEBOOK_PAGE_ACCESS_TOKEN,
            },
            timeout=30,
        )
        if create_resp.status_code != 200:
            return f"Instagram media create {create_resp.status_code}: {create_resp.text[:200]}"
        creation_id = create_resp.json().get("id")
        if not creation_id:
            return f"Instagram media create: no id in response: {create_resp.text[:200]}"

        # Step 2: publish
        publish_resp = requests.post(
            f"https://graph.facebook.com/v19.0/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/media_publish",
            params={
                "creation_id": creation_id,
                "access_token": FACEBOOK_PAGE_ACCESS_TOKEN,
            },
            timeout=30,
        )
        if publish_resp.status_code == 200:
            post_id = publish_resp.json().get("id", "?")
            log.info("Instagram post published: id=%s", post_id)
            return None
        return f"Instagram publish {publish_resp.status_code}: {publish_resp.text[:200]}"
    except Exception as e:
        log.warning("Instagram post failed: %s", e)
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


def post_approved_draft(platform: str, draft: dict) -> dict:
    """
    Dispatch an approved draft to the correct platform(s).

    platform: "linkedin" | "facebook" | "instagram" | "twitter" | "all"

    For each platform:
      - Try direct API first.
      - If not configured (returns "not configured"), try Make.com.
      - If Make.com also not configured, log warning and record as "skipped".

    Returns dict of {platform: "ok" | error_str} for all attempted platforms.
    """
    results: dict = {}
    image_url = draft.get("og_image_url", "")

    def _dispatch(plat: str) -> str:
        """Attempt direct API, fall back to Make.com. Returns "ok" or error string."""
        error: str | None = None

        if plat == "linkedin":
            error = post_to_linkedin(draft.get("linkedin", ""))
        elif plat == "facebook":
            error = post_to_facebook(draft.get("facebook", ""), link=draft.get("url", ""))
        elif plat == "instagram":
            caption = draft.get("instagram", "")
            error = post_to_instagram(caption, image_url)
        elif plat == "twitter":
            error = post_to_twitter(draft.get("twitter", ""))
        else:
            return f"unknown platform: {plat}"

        if error is None:
            return "ok"

        # Direct API not configured or failed — try Make.com
        if error == "not configured":
            log.info("%s direct API not configured — trying Make.com", plat)
        else:
            log.warning("%s direct post failed (%s) — trying Make.com", plat, error)

        make_err = post_via_make(
            plat,
            draft.get(plat, ""),
            draft,
            instagram_caption=draft.get("instagram", "") if plat == "instagram" else "",
            image_url=image_url,
        )
        if make_err is None:
            return "ok (via make)"
        if make_err == "not configured":
            log.warning("%s: neither direct API nor Make.com configured — skipping", plat)
            return "skipped: not configured"
        return f"make error: {make_err}"

    platforms_to_try = ["linkedin", "facebook", "instagram", "twitter"] if platform == "all" else [platform]

    for plat in platforms_to_try:
        results[plat] = _dispatch(plat)
        log.info("post_approved_draft result: platform=%s result=%s entity=%s", plat, results[plat], draft.get("entity", "?"))

    return results
