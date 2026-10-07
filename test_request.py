import sys
import json
import requests

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

print("📡 Sending request to http://127.0.0.1:8001/predict-risk...")
try:
    response = requests.post(
        "http://127.0.0.1:8001/predict-risk",
        json={"query_description": "I slept for only 3 hours and my heart rate is spiking"},
        timeout=35
    )
    
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print("\n" + "="*50)
        print("🤖 GEMINI CLINICAL REPORT:")
        print("="*50)
        print(data.get("gemini_report"))
        print("\n" + "="*50)
        print(f"📚 Retrieved Rules Count: {len(data.get('raw_retrieved_rules', []))}")
        print("="*50)
    else:
        print(f"Error Response ({response.status_code}):", response.text)
except requests.exceptions.Timeout:
    print("❌ Request timed out after 35 seconds.")
except requests.exceptions.ConnectionError:
    print("❌ Connection error: Is the server running on port 8001? Run 'python querry.py' first.")
except Exception as e:
    print(f"❌ Unexpected error: {e}")