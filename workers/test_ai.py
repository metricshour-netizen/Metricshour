"""Quick smoke test — verifies Gemini + DeepSeek keys are live and responding."""
import os, sys, requests
from dotenv import load_dotenv

load_dotenv('/root/metricshour/backend/.env')

GEMINI_KEY_1 = os.environ.get("GEMINI_API_KEY", "")
GEMINI_KEY_2 = os.environ.get("GEMINI_API_KEY_2", "")
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

PROMPT = "Reply with exactly: OK"


def test_gemini(key: str, label: str, model: str = "gemini-2.5-flash") -> str:
    if not key:
        return "MISSING"
    try:
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            params={"key": key},
            json={"contents": [{"parts": [{"text": PROMPT}]}],
                  "generationConfig": {"maxOutputTokens": 500}},
            timeout=20,
        )
        if r.status_code == 200:
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            return f"OK — {text[:30]!r}"
        return f"HTTP {r.status_code}: {r.text[:100]}"
    except Exception as e:
        return f"ERROR: {e}"


def test_deepseek(key: str) -> str:
    if not key:
        return "MISSING"
    try:
        r = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": "deepseek-chat",
                  "messages": [{"role": "user", "content": PROMPT}],
                  "max_tokens": 20},
            timeout=20,
        )
        if r.status_code == 200:
            text = r.json()["choices"][0]["message"]["content"].strip()
            return f"OK — {text[:30]!r}"
        return f"HTTP {r.status_code}: {r.text[:100]}"
    except Exception as e:
        return f"ERROR: {e}"


print("=== AI KEY STATUS ===")
print(f"GEMINI_API_KEY:    {'SET' if GEMINI_KEY_1 else 'MISSING'}")
print(f"GEMINI_API_KEY_2:  {'SET' if GEMINI_KEY_2 else 'MISSING'}")
print(f"DEEPSEEK_API_KEY:  {'SET' if DEEPSEEK_KEY else 'MISSING'}")
print(f"ANTHROPIC_API_KEY: {'SET (unused)' if ANTHROPIC_KEY else 'MISSING'}")

print("\n=== LIVE TESTS ===")
print(f"Gemini key1 (flash):      {test_gemini(GEMINI_KEY_1, 'key1', 'gemini-2.5-flash')}")
print(f"Gemini key1 (flash-lite): {test_gemini(GEMINI_KEY_1, 'key1', 'gemini-2.5-flash-lite')}")
print(f"Gemini key2 (flash):      {test_gemini(GEMINI_KEY_2, 'key2', 'gemini-2.5-flash')}")
print(f"DeepSeek V3:              {test_deepseek(DEEPSEEK_KEY)}")

# Exit non-zero if any primary key is broken
ok = (
    test_gemini(GEMINI_KEY_1, 'key1').startswith("OK") if GEMINI_KEY_1 else False
) or (
    test_deepseek(DEEPSEEK_KEY).startswith("OK") if DEEPSEEK_KEY else False
)
sys.exit(0 if ok else 1)
