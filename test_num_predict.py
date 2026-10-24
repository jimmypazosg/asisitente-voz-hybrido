import time
import requests

url = "http://127.0.0.1:11434/api/generate"
prompt = "Dime qué hora es o responde brevemente"

t0 = time.time()
res = requests.post(
    url,
    json={
        "model": "qwen3.5:9b",
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": 100,
            "num_ctx": 2048
        }
    },
    timeout=60
)
elapsed = time.time() - t0
data = res.json()
print(f"Tiempo: {elapsed:.2f}s")
print("Response text:", repr(data.get("response")))
