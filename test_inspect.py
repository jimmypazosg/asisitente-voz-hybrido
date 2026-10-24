import requests
import json

res = requests.post(
    "http://127.0.0.1:11434/api/generate",
    json={"model": "qwen3.5:9b", "prompt": "¿Hola?", "stream": False}
)
d = res.json()
print("Keys:", list(d.keys()))
for k in ["response", "thinking", "message", "done_reason", "eval_count"]:
    print(f"{k}: {repr(d.get(k))}")
