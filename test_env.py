import ctranslate2
import pyttsx3
import sounddevice as sd
from faster_whisper import WhisperModel

print("--- VERIFICACIÓN CUDA ---")
cuda_count = ctranslate2.get_cuda_device_count()
print(f"GPUs NVIDIA detectadas por CTranslate2: {cuda_count}")

device = "cuda" if cuda_count > 0 else "cpu"
compute_type = "float16" if device == "cuda" else "int8"
print(f"Dispositivo a usar: {device} (compute_type: {compute_type})")

print("\n--- CARGANDO MODELO FASTER-WHISPER (tiny / base) ---")
# Usamos 'base' para prueba rápida y descarga inicial
try:
    model = WhisperModel("base", device=device, compute_type=compute_type)
    print("¡Modelo Whisper cargado exitosamente en", device, "!")
except Exception as e:
    print(f"Error cargando en {device}: {e}. Probando CPU...")
    model = WhisperModel("base", device="cpu", compute_type="int8")
    print("¡Modelo Whisper cargado exitosamente en CPU!")

print("\n--- PRUEBA DE VOZ SAPI5 (Helena - Español) ---")
engine = pyttsx3.init()
voices = engine.getProperty("voices")
for v in voices:
    if "helena" in v.name.lower() or "spanish" in v.name.lower():
        engine.setProperty("voice", v.id)
        print(f"Voz seleccionada: {v.name}")
        break

engine.setProperty("rate", 175) # Velocidad natural
print("Sistema listo para hablar y escuchar.")
