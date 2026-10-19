"""Check that your Gemini API key works. Sends only a harmless test prompt.

Set the key for this PowerShell window first (never paste it into a file or a chat):
    $env:GEMINI_API_KEY="your-key"
Optional: choose a model with  $env:GEMINI_MODEL="gemini-2.5-flash-lite"
Run:  python scripts\test_gemini_key.py
"""
import json
import os
import sys

import requests

BASE = "https://generativelanguage.googleapis.com/v1beta"


def explain(status: int, body: str) -> str:
    hints = {
        400: "Bad request. If it mentions the API key, the key was copied wrongly: create it again and re-set it.",
        403: "Permission denied. The key may be restricted, or the API may be unavailable for your account or country.",
        404: "Model not found. Pick a name from the list printed above and set GEMINI_MODEL.",
        429: "Rate limit reached. Wait a minute and run again. The free tier is strict.",
    }
    return f"HTTP {status}. {hints.get(status, '')}\n{body[:300]}"


def main():
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        sys.exit('No key found. In PowerShell run: $env:GEMINI_API_KEY="your-key"')
    headers = {"x-goog-api-key": key, "Content-Type": "application/json"}

    r = requests.get(f"{BASE}/models", headers=headers, timeout=30)
    if r.status_code != 200:
        sys.exit("Listing models failed. " + explain(r.status_code, r.text))
    models = [m["name"].split("/")[-1] for m in r.json().get("models", [])
              if "generateContent" in m.get("supportedGenerationMethods", [])]
    flash = sorted(m for m in models if "flash" in m)
    print(f"Key works. {len(models)} models can generate text. Flash models you can use:")
    for m in flash:
        print("  ", m)

    model = os.environ.get("GEMINI_MODEL") or next((m for m in flash if "lite" in m), None) or (flash[0] if flash else None)
    if not model:
        sys.exit("No flash model found. Set GEMINI_MODEL to one of the models above.")
    print(f"\nTesting model: {model}")

    payload = {
        "contents": [{"parts": [{"text": 'Return exactly this JSON and nothing else: {"ok": true, "word": "ready"}'}]}],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
    }
    r = requests.post(f"{BASE}/models/{model}:generateContent", headers=headers, json=payload, timeout=60)
    if r.status_code != 200:
        sys.exit("Test prompt failed. " + explain(r.status_code, r.text))
    try:
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        parsed = json.loads(text)
    except Exception:
        sys.exit("The call worked but the reply was not valid JSON:\n" + r.text[:400])
    print("Reply parsed as JSON:", parsed)
    print("\nAll good. Your key and model work.")


if __name__ == "__main__":
    main()
