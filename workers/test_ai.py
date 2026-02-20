import os
from dotenv import load_dotenv
from google import genai

load_dotenv('/root/metricshour/backend/.env')

client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])

try:
    response = client.models.generate_content(
        model="gemini-2.0-flash", 
        contents="Confirm: Finland Node is live and ready for MetricsHour."
    )
    print(f"TERMINAL FEED: {response.text}")
except Exception as e:
    print(f"TERMINAL ERROR: {e}")
