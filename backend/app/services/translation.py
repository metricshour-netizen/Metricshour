"""
TranslationService — Gemini-powered translation with Redis cache.

Cache key pattern: translation:{lang}:{content_hash}
TTLs:
  static page content  → 30 days
  dynamic insights     → 24 hours
  meta titles/descs    → 30 days
  ui strings           → 7 days
"""
import hashlib
import json
import logging

import httpx

from app.config import settings
from app.storage import redis_json_get, redis_json_set

logger = logging.getLogger(__name__)

# TTL constants (seconds)
TTL_STATIC = 60 * 60 * 24 * 30   # 30 days
TTL_DYNAMIC = 60 * 60 * 24        # 24 hours
TTL_META = 60 * 60 * 24 * 30      # 30 days
TTL_UI = 60 * 60 * 24 * 7         # 7 days

LANGUAGE_NAMES = {
    "es": "Spanish",
    "pt": "Portuguese",
    "fr": "French",
    "de": "German",
    "ar": "Arabic",
    "zh": "Chinese (Simplified)",
}

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

_PROMPT_TEMPLATE = (
    "Translate the following financial content into {language}. Rules:\n"
    "- Use professional financial terminology\n"
    "- Preserve all numbers, percentages exactly\n"
    "- Preserve ticker symbols exactly (AAPL, NVDA etc.)\n"
    "- Preserve currency values exactly ($3.3T etc.)\n"
    "- Do not translate: ticker symbols, data source names (World Bank, IMF, "
    "SEC EDGAR, UN Comtrade), country codes (US, CN, DE etc.)\n"
    "- Return translated text only\n"
    "- No explanation, no preamble\n"
    "Content: {content}"
)


def _cache_key(lang: str, content: str) -> str:
    h = hashlib.sha256(content.encode()).hexdigest()[:16]
    return f"translation:{lang}:{h}"


async def translate(content: str, lang: str, ttl: int = TTL_STATIC) -> str:
    """
    Translate content to lang. Returns English on any failure.
    Checks Redis cache first — never calls Gemini for cached content.
    """
    if lang == "en" or not content or not content.strip():
        return content

    if lang not in LANGUAGE_NAMES:
        logger.warning("Unsupported translation language: %s", lang)
        return content

    if not settings.gemini_api_key:
        return content

    cache_key = _cache_key(lang, content)
    cached = redis_json_get(cache_key)
    if cached is not None:
        return cached

    language_name = LANGUAGE_NAMES[lang]
    prompt = _PROMPT_TEMPLATE.format(language=language_name, content=content)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                GEMINI_URL,
                params={"key": settings.gemini_api_key},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2048},
                },
            )
            resp.raise_for_status()
            data = resp.json()
            translated = data["candidates"][0]["content"]["parts"][0]["text"].strip()

        redis_json_set(cache_key, translated, ttl_seconds=ttl)
        logger.info("Translated %d chars to %s (cache miss)", len(content), lang)
        return translated

    except Exception as exc:
        logger.error("Translation failed for lang=%s: %s", lang, exc)
        return content


async def translate_batch(items: dict[str, str], lang: str, ttl: int = TTL_STATIC) -> dict[str, str]:
    """
    Translate a dict of {key: text} in a single Gemini call.
    Returns {key: translated_text}. Falls back to English on failure.
    Passes all items as a JSON block to minimise API calls.
    """
    if lang == "en" or not items:
        return items

    # Check which are already cached
    result: dict[str, str] = {}
    to_translate: dict[str, str] = {}

    for k, v in items.items():
        cache_key = _cache_key(lang, v)
        cached = redis_json_get(cache_key)
        if cached is not None:
            result[k] = cached
        else:
            to_translate[k] = v

    if not to_translate:
        return result

    # Single API call for all uncached items
    combined = json.dumps(to_translate, ensure_ascii=False)
    translated_raw = await translate(combined, lang, ttl)

    try:
        translated_dict: dict[str, str] = json.loads(translated_raw)
        for k, v in translated_dict.items():
            if k in to_translate:
                cache_key = _cache_key(lang, to_translate[k])
                redis_json_set(cache_key, v, ttl_seconds=ttl)
                result[k] = v
    except Exception:
        # Parsing failed — fall back to English for untranslated items
        result.update(to_translate)

    return result
