import os
import sys

print("Configurando DLLs de NVIDIA...")
if sys.platform == "win32":
    venv_dir = os.path.dirname(sys.executable)
    # site-packages puede estar en .venv/Lib/site-packages/nvidia
    base_dir = os.path.dirname(venv_dir)
    site_packages = os.path.join(base_dir, "Lib", "site-packages", "nvidia")
    print("Buscando en:", site_packages)
    if os.path.exists(site_packages):
        for root, dirs, files in os.walk(site_packages):
            if os.path.basename(root) == "bin":
                print("Agregando DLL dir:", root)
                try:
                    os.add_dll_directory(root)
                    os.environ["PATH"] = root + os.pathsep + os.environ["PATH"]
                except Exception as e:
                    print("Error agregando:", e)

import numpy as np
from faster_whisper import WhisperModel

print("Cargando Whisper base en CUDA float16...")
model = WhisperModel("base", device="cuda", compute_type="float16")
print("Transcribiendo array de prueba (1 segundo de silencio)...")
segs, info = model.transcribe(np.zeros(16000, dtype=np.float32), language="es")
list(segs)
print("¡ÉXITO TOTAL! Whisper transcribió en GPU con CUDA sin ningún error.")
