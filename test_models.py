import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.environ.get("GEMINI_API_KEY")

if not api_key:
    print("No GEMINI_API_KEY found.")
    exit(1)

client = genai.Client(api_key=api_key)
try:
    for model in client.models.list():
        if "flash" in model.name:
            print(model.name)
except Exception as e:
    print(f"Error listing models: {e}")
