import time
import requests

url = "http://127.0.0.1:11434/api/generate"
prompt = "si arrarmeno de inicio"
print(f"Probando Ollama con prompt: '{prompt}'...")

t0 = time.time()
try:
    res = requests.post(
        url,
        json={
            "model": "qwen3.5:9b",
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_ctx": 2048
            }
        },
        timeout=120
    )
    elapsed = time.time() - t0
    print(f"Status: {res.status_code} en {elapsed:.2f}s")
    if res.status_code == 200:
        data = res.json()
        print("Respuesta:", data.get("response", ""))
        print("Stats:", data.get("eval_count"), "tokens a", (data.get("eval_count", 0) / (data.get("eval_duration", 1) / 1e9)), "tps")
except Exception as e:
    print("Error:", e)
