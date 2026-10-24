import os
import sys

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def hablar_kokoro(texto, voz="ef_dora", velocidad=1.05):
    import kokoro_onnx
    import sounddevice as sd

    base_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(base_dir, "models", "kokoro", "kokoro-v1.0.onnx")
    voices_path = os.path.join(base_dir, "models", "kokoro", "voices-v1.0.bin")

    print(f"⚡ Inicializando Kokoro TTS...")
    kokoro = kokoro_onnx.Kokoro(model_path, voices_path)

    # Mapeo amigable de nombres
    if voz in ("dora", "femenina", "mujer"):
        voz = "ef_dora"
    elif voz in ("alex", "masculina", "hombre"):
        voz = "em_alex"
    elif voz in ("santa",):
        voz = "em_santa"

    print(f"🎙️ Voz activa: Kokoro [{voz}] (Español)")
    print(f"🔊 Hablando: '{texto}'")
    samples, sample_rate = kokoro.create(texto, voice=voz, lang="es", speed=velocidad)
    sd.play(samples, sample_rate)
    sd.wait()

def hablar_sapi(texto, nombre_voz="laura"):
    import win32com.client
    import pythoncom
    pythoncom.CoInitialize()
    voice = None
    try:
        cat = win32com.client.Dispatch("SAPI.SpObjectTokenCategory")
        cat.SetId(r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech_OneCore\Voices")
        tokens = cat.EnumerateTokens()
        
        token_elegido = None
        for i in range(tokens.Count):
            t = tokens.Item(i)
            if nombre_voz.lower() in t.GetDescription().lower():
                token_elegido = t
                break

        voice = win32com.client.Dispatch("SAPI.SpVoice")
        if token_elegido:
            voice.Voice = token_elegido
            print(f"🎙️ Voz activa: {voice.Voice.GetDescription()}")

        voice.Rate = 1
        voice.Volume = 100
        print(f"🔊 Hablando (SAPI): '{texto}'")
        voice.Speak(texto)
    finally:
        voice = None
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass

if __name__ == "__main__":
    param = sys.argv[1].lower() if len(sys.argv) > 1 else "dora"
    if param in ("laura", "pablo", "helena"):
        hablar_sapi(f"Hola, esta es la voz tradicional de Windows {param}.", nombre_voz=param)
    else:
        hablar_kokoro(
            "Hola, esta es una prueba del modelo de voz neuronal Kokoro. ¿Qué te parece cómo suena mi entonación?",
            voz=param,
            velocidad=1.05
        )



