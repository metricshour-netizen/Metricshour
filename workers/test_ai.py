import os
from dotenv import load_dotenv
from google import genai

load_dotenv('/root/metricshour/backend/.env')

_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY_2", "")
if not _key:
    print("ERROR: No GEMINI_API_KEY set in .env")
    exit(1)
client = genai.Client(api_key=_key)

try:
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Confirm: Finland Node is live and ready for MetricsHour."
    )
    print(f"TERMINAL FEED: {response.text}")
except Exception as e:
    print(f"TERMINAL ERROR: {e}")
