# from anthropic import Anthropic
# import os

# CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY", "")
# client = Anthropic(api_key=CLAUDE_API_KEY)
# models = client.models.list()  # check the docs for exact method
# print([m.id for m in models.data])

import os
import json
import urllib.request
import urllib.error

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("Please set GEMINI_API_KEY environment variable")

url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"

try:
    with urllib.request.urlopen(url) as response:
        if response.status != 200:
            raise RuntimeError(f"Request failed with status {response.status}")
        data = json.loads(response.read().decode("utf-8"))

    print("Available Gemini models:")
    for model in data.get("models", []):
        name = model.get("name")
        display_name = model.get("displayName", "")
        description = model.get("description", "")
        print(f"- {name}")
        if display_name:
            print(f"  Display Name: {display_name}")
        if description:
            print(f"  Description: {description}")
        print()

except urllib.error.HTTPError as e:
    print("HTTP Error:", e.code, e.reason)
except urllib.error.URLError as e:
    print("Connection Error:", e.reason)
except Exception as e:
    print("Unexpected error:", e)
