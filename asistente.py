import json
import os
import sys
import threading
import time
import winsound

import ctypes

if sys.platform == "win32":
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
else:
    user32 = None
    kernel32 = None

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    # Desactivar QuickEdit mode para que clics del ratón en la consola no congelen la ejecución
    try:
        kernel32 = ctypes.windll.kernel32
        h_stdin = kernel32.GetStdHandle(-10) # STD_INPUT_HANDLE
        mode = ctypes.c_ulong()
        if kernel32.GetConsoleMode(h_stdin, ctypes.byref(mode)):
            new_mode = (mode.value & ~0x0040) | 0x0080
            kernel32.SetConsoleMode(h_stdin, new_mode)
    except Exception:
        pass

    # Registrar DLLs de NVIDIA CUDA 12 y cuDNN instaladas en el entorno
    try:
        venv_dir = os.path.dirname(sys.executable)
        base_dir = os.path.dirname(venv_dir)
        nvidia_pkg_dir = os.path.join(base_dir, "Lib", "site-packages", "nvidia")
        if os.path.exists(nvidia_pkg_dir):
            for root, dirs, files in os.walk(nvidia_pkg_dir):
                if os.path.basename(root) == "bin":
                    try:
                        os.add_dll_directory(root)
                        os.environ["PATH"] = root + os.pathsep + os.environ["PATH"]
                    except Exception:
                        pass
    except Exception:
        pass

import re
import random
from datetime import datetime
import numpy as np
import pythoncom
import pyttsx3
import win32com.client
import requests
import sounddevice as sd
from faster_whisper import WhisperModel
from pynput import keyboard

import logging
import acciones
import hud as hud_module

# Configurar logging persistente a archivo y consola
LOG_PATH = os.path.join(os.path.dirname(__file__), "asistente.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("asistente")

# Cargar configuración (crea config.json desde plantilla si no existe)
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
EXAMPLE_PATH = os.path.join(os.path.dirname(__file__), "config.example.json")

if not os.path.exists(CONFIG_PATH) and os.path.exists(EXAMPLE_PATH):
    import shutil
    shutil.copyfile(EXAMPLE_PATH, CONFIG_PATH)
    logger.info("config.json inicializado desde config.example.json")

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = json.load(f)

print("=" * 60)
print("🎙️  ASISTENTE DE VOZ LOCAL (Whisper + Ollama + Síntesis)")
print("=" * 60)

# Limpieza de texto para evitar errores de codificación charmap y pronunciación en Windows
def limpiar_texto(texto):
    if not texto:
        return ""
    patron_emojis = re.compile(
        "[\U00010000-\U0010ffff"
        "\u2600-\u26ff"
        "\u2700-\u27bf"
        "\ufe00-\ufe0f"
        "\u200d"
        "\u2300-\u23ff]+",
        flags=re.UNICODE
    )
    t = patron_emojis.sub("", texto)
    t = t.replace("**", "").replace("*", "").replace("#", "").replace("`", "")
    return t.strip()

def adaptar_pronunciacion(texto):
    """Adapta palabras clave para que el sintetizador en español las pronuncie como en inglés o con la entonación óptima."""
    if not texto:
        return ""
    t = texto
    # Jimmy en inglés suena 'Yimi' en la fonética española de Kokoro y Windows, evitando la J fuerte castellana
    t = re.sub(r'\bJimmy\b', 'Yimi', t, flags=re.IGNORECASE)
    # Asegurar acento natural en Biktus
    t = re.sub(r'\bBiktus\b', 'Víktus', t, flags=re.IGNORECASE)
    return t

# 1. Configurar Síntesis de Voz (TTS)
tts_lock = threading.Lock()
tts_engine_type = config.get("tts_engine", "kokoro").lower()
kokoro_model = None

if tts_engine_type == "kokoro":
    try:
        import kokoro_onnx
        base_dir = os.path.dirname(os.path.abspath(__file__))
        k_model_path = os.path.join(base_dir, "models", "kokoro", "kokoro-v1.0.onnx")
        k_voices_path = os.path.join(base_dir, "models", "kokoro", "voices-v1.0.bin")
        if os.path.exists(k_model_path) and os.path.exists(k_voices_path):
            voz_cfg = config.get("tts_voice", "ef_dora")
            print(f"⚡ Inicializando voz neuronal Kokoro-82M (local offline) [{voz_cfg}]...")
            kokoro_model = kokoro_onnx.Kokoro(k_model_path, k_voices_path)
            try:
                kokoro_model.create("ok", voice=voz_cfg, lang="es")
            except Exception:
                pass
            print(f"✅ Biktus TTS listo (Voz: {voz_cfg}).")
        else:
            print("⚠️ Archivos de Kokoro no encontrados, recurriendo a voces de Windows.")
    except Exception as e:
        print(f"⚠️ Error cargando Kokoro ({e}), recurriendo a voces de Windows.")

def hablar(texto):
    """Pronuncia el texto usando Kokoro neuronal (offline) o voces OneCore/SAPI5 de Windows."""
    texto_limpio = limpiar_texto(texto)
    if not texto_limpio:
        return

    def _hablar():
        with tts_lock:
            nombre_asistente = config.get("assistant_name", "Biktus")
            texto_fonetico = adaptar_pronunciacion(texto_limpio)

            # 1. Intentar con Kokoro Neuronal
            if kokoro_model is not None:
                try:
                    voz_k = config.get("tts_voice", "ef_dora")
                    vel_k = float(config.get("tts_speed", 1.05))
                    print(f"🔊 {nombre_asistente}: \"{texto_limpio}\"")
                    samples, sr = kokoro_model.create(texto_fonetico, voice=voz_k, lang="es", speed=vel_k)
                    sd.play(samples, sr)
                    sd.wait()
                    return
                except Exception as k_err:
                    print(f"⚠️ Error en Kokoro ({k_err}), recurriendo a voz de respaldo...")

            # 2. Respaldo: Windows OneCore / SAPI5
            voice = None
            cat = None
            tokens = None
            token_elegido = None
            try:
                pythoncom.CoInitialize()
                voz_deseada = str(config.get("tts_voice", "laura")).lower()
                try:
                    cat = win32com.client.Dispatch("SAPI.SpObjectTokenCategory")
                    cat.SetId(r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech_OneCore\Voices")
                    tokens = cat.EnumerateTokens()
                    for i in range(tokens.Count):
                        t = tokens.Item(i)
                        desc = t.GetDescription().lower()
                        if voz_deseada in desc:
                            token_elegido = t
                            break
                    if not token_elegido:
                        for i in range(tokens.Count):
                            t = tokens.Item(i)
                            if "spanish" in t.GetDescription().lower() or "es" in t.Id.lower():
                                token_elegido = t
                                break
                except Exception:
                    token_elegido = None

                voice = win32com.client.Dispatch("SAPI.SpVoice")
                if token_elegido:
                    voice.Voice = token_elegido

                rate_cfg = config.get("tts_rate", 1)
                if isinstance(rate_cfg, (int, float)) and rate_cfg > 10:
                    voice_rate = int((rate_cfg - 150) / 30)
                    voice_rate = max(-10, min(10, voice_rate))
                else:
                    voice_rate = int(rate_cfg)
                voice.Rate = voice_rate

                vol_cfg = config.get("tts_volume", 1.0)
                if isinstance(vol_cfg, (int, float)) and vol_cfg <= 1.0:
                    voice.Volume = int(vol_cfg * 100)
                else:
                    voice.Volume = int(vol_cfg)

                nombre_voz = voice.Voice.GetDescription() if voice.Voice else "Predeterminada"
                print(f"🔊 {nombre_asistente} ({nombre_voz}): \"{texto_limpio}\"")
                voice.Speak(texto_fonetico)
            except Exception as err:
                print(f"⚠️ Error en TTS de respaldo: {err}")
            finally:
                voice = None
                token_elegido = None
                tokens = None
                cat = None
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass
    threading.Thread(target=_hablar, daemon=True).start()

def sonar_pitido(frecuencia, duracion):
    """Emite un pequeño pitido indicador solo si está habilitado en config."""
    if not config.get("sonido_pitido", False):
        return
    threading.Thread(target=winsound.Beep, args=(frecuencia, duracion), daemon=True).start()

# 2. Cargar Whisper en GPU RTX 4060
device = config.get("device", "cuda")
compute_type = config.get("compute_type", "float16")
model_size = config.get("whisper_model", "small")

print(f"⚡ Inicializando Whisper ({model_size}) en dispositivo [{device.upper()}]...")
try:
    whisper_model = WhisperModel(model_size, device=device, compute_type=compute_type)
    print(f"✅ Whisper cargado en {device.upper()} con cómputo {compute_type}.")
except Exception as e:
    print(f"⚠️ No se pudo cargar en {device}: {e}. Recurriendo a CPU...")
    whisper_model = WhisperModel(model_size, device="cpu", compute_type="int8")
    print("✅ Whisper cargado en CPU.")

# 3. Estado de Grabación y Audio
sample_rate = config.get("audio_sample_rate", 16000)
audio_frames = []
is_recording = False
recording_lock = threading.Lock()

# Inicializar HUD Flotante Visual
hud = None
if config.get("hud_visual", True):
    try:
        hud = hud_module.FloatingHUD()
        print("✅ HUD Flotante Visual listo (animación ecualizador activa).")
    except Exception as e:
        logger.warning(f"No se pudo inicializar HUD visual: {e}")

def audio_callback(indata, frames, time_info, status):
    if is_recording:
        audio_frames.append(indata.copy())
        if hud is not None:
            try:
                rms = float(np.sqrt(np.mean(indata**2)))
                hud.actualizar_volumen(rms)
            except Exception:
                pass

audio_stream = sd.InputStream(
    samplerate=sample_rate,
    channels=1,
    dtype="float32",
    callback=audio_callback
)
audio_stream.start()

# 4. Procesamiento de Texto y Router de Acciones
def normalizar(texto):
    t = texto.lower().strip()
    for char in [".", ",", "¡", "!", "¿", "?", ":", ";", "-"]:
        t = t.replace(char, "")
    return " ".join(t.split())

def es_intencion_cerrar(texto):
    """Detecta si la frase indica cerrar, terminar, apagar o salir de una app."""
    palabras = [
        "cerrar", "cierra", "cierres", "cierralo", "ciérralo", "cierrala", "ciérrala",
        "sierra", "serra", "quitar", "quita", "apagar", "apaga", "terminar", "termina",
        "matar", "mata", "finalizar", "finaliza"
    ]
    for p in palabras:
        if re.search(rf"\b{p}\b", texto):
            return True
    return False

def es_intencion_abrir(texto):
    """Detecta si la frase expresa intención de abrir o iniciar una app."""
    palabras = [
        "abrir", "abre", "abres", "abreme", "ábreme", "iniciar", "inicia",
        "ejecutar", "ejecuta", "lanzar", "lanza", "poner", "pon", "labre"
    ]
    for p in palabras:
        if re.search(rf"\b{p}\b", texto):
            return True
    return False

def generar_saludo_dinamico():
    """Genera saludos variados y cercanos según la hora del día, con toques en Spanglish y apodos."""
    hora_actual = datetime.now().hour
    user_name = config.get("user_name", "Jimmy")
    nickname = config.get("user_nickname", "Mochi")
    # Alternancia natural: 65% Jimmy, 35% Mochi
    nombre = nickname if random.random() < 0.35 else user_name

    if 5 <= hora_actual < 12:
        saludos = [
            f"Good morning, {nombre}! Todo ready para empezar el día. ¿Qué hacemos hoy?",
            f"Buenos días, {nombre}! Biktus al 100%, listo para lo que necesites.",
            f"Hey {nombre}, buenos días! Espero que hayas descansado genial. ¿En qué te colaboro?",
            f"Good morning, {nombre}! Sistema activo y a tu servicio. ¿Qué mandas hoy?"
        ]
    elif 12 <= hora_actual < 20:
        saludos = [
            f"Buenas tardes, {nombre}! ¿Qué tal va la jornada?",
            f"Hey {nombre}! Todo cool por aquí en tu Victus. ¿Qué necesitas que hagamos?",
            f"Buenas tardes, {nombre}! Biktus a la orden, dime en qué te ayudo.",
            f"Qué onda, {nombre}! Todo ready por acá. Dime qué hacemos."
        ]
    else:
        saludos = [
            f"Buenas noches, {nombre}! ¿Seguimos dándole o ya casi a descansar?",
            f"Hey {nombre}, buenas noches! Biktus activo por aquí si necesitas algo.",
            f"Buenas noches, {nombre}! Todo tranqui por aquí. ¿En qué te colaboro hoy?",
            f"Buenas noches, {nombre}! All good por acá, dime qué necesitas."
        ]
    return random.choice(saludos)

def consultar_ollama(prompt):
    """Consulta a Ollama localmente para preguntas generales o comandos abiertos."""
    url = config.get("ollama_url", "http://127.0.0.1:11434/api/generate")
    model = config.get("ollama_model", "qwen3.5:9b")
    asistente_nombre = config.get("assistant_name", "Biktus")
    user_name = config.get("user_name", "Jimmy")
    nickname = config.get("user_nickname", "Mochi")
    print(f"🤖 {asistente_nombre} consultando a Ollama ({model})...")
    
    system_prompt = (
        f"Tu nombre es {asistente_nombre}, el asistente de voz inteligente de una laptop HP Victus en Windows 11. "
        f"Tu usuario y amigo se llama {user_name} (se pronuncia en inglés como Djimmi). De cariño sus familiares le dicen {nickname}, "
        f"así que puedes llamarlo {user_name} o de vez en cuando {nickname}. "
        f"Tu personalidad es fresca, cercana, tecnológica y con muy buena vibra. "
        f"Hablas en español pero te gusta usar de forma natural y ligera expresiones en Spanglish (como 'Hey {user_name}', 'todo ready', 'cool', 'all right', 'perfecto'). "
        f"Responde siempre de forma muy concisa y directa (máximo 1 o 2 oraciones breves), "
        f"sin usar emojis, markdown, asteriscos ni listas numeradas, ya que tu respuesta será leída por un sintetizador de voz."
    )
    
    try:
        res = requests.post(
            url,
            json={
                "model": model,
                "system": system_prompt,
                "prompt": prompt,
                "stream": False,
                "think": False,
                "options": {
                    "temperature": 0.4,
                    "num_predict": 120,
                    "num_ctx": 2048
                }
            },
            timeout=30
        )
        if res.status_code == 200:
            data = res.json()
            respuesta = data.get("response", "").strip()
            if not respuesta and data.get("thinking"):
                respuesta = data.get("thinking", "").strip()
            return limpiar_texto(respuesta)
        else:
            return f"Ollama respondió con error {res.status_code}."
    except Exception as e:
        return f"No pude conectar con Ollama: {e}"

def guardar_config():
    """Guarda la configuración actualizada de forma persistente en config.json."""
    try:
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        logger.info("💾 Configuración persistida en config.json.")
    except Exception as e:
        logger.error(f"Error al guardar config.json: {e}")

def consultar_gemini(prompt):
    """Consulta a Google Gemini en la nube usando el SDK oficial google-genai."""
    api_key = config.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY") or ""
    if not api_key.strip():
        return "No tengo configurada la clave API de Gemini en config.json."
    
    asistente_nombre = config.get("assistant_name", "Biktus")
    user_name = config.get("user_name", "Jimmy")
    nickname = config.get("user_nickname", "Mochi")
    model_name = config.get("gemini_model", "gemini-3.8-flash")
    print(f"☁️ {asistente_nombre} consultando a Gemini en la nube ({model_name})...")

    system_prompt = (
        f"Tu nombre es {asistente_nombre}, el asistente de voz inteligente de una laptop HP Victus en Windows 11. "
        f"Tu usuario y amigo se llama {user_name} (se pronuncia en inglés como Djimmi). De cariño sus familiares le dicen {nickname}, "
        f"así que puedes llamarlo {user_name} o de vez en cuando {nickname}. "
        f"Tu personalidad es fresca, cercana, tecnológica y con muy buena vibra. "
        f"Hablas en español pero te gusta usar de forma natural y ligera expresiones en Spanglish (como 'Hey {user_name}', 'todo ready', 'cool', 'all right', 'perfecto'). "
        f"Responde siempre de forma muy concisa y directa (máximo 1 o 2 oraciones breves), "
        f"sin usar emojis, markdown, asteriscos ni listas numeradas, ya que tu respuesta será leída por un sintetizador de voz."
    )

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=1000,
                temperature=0.4
            )
        )
        texto = response.text or ""
        return limpiar_texto(texto)
    except Exception as e:
        logger.error(f"Error al conectar con Gemini: {e}")
        return f"Error al conectar con Gemini: {e}"

def consultar_cerebro(prompt):
    """Enruta la consulta a Gemini (nube) o a Ollama (local) según el modo activo."""
    modo = config.get("brain_mode", "local").lower()
    if modo == "cloud":
        api_key = config.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY") or ""
        if api_key.strip():
            hablar("Consultando en la nube...")
            respuesta = consultar_gemini(prompt)
            if respuesta and not respuesta.startswith("Error"):
                return respuesta
            print(f"⚠️ Falló consulta a Gemini. Recurriendo a Ollama local...")
            hablar("Sin conexión con Gemini, procesando en local...")
        else:
            hablar("Falta la clave de Gemini en config.json, respondiendo con Ollama...")

    hablar("Procesando consulta...")
    return consultar_ollama(prompt)

modo_dictado_continuo = False

DICCIONARIO_TECNOLOGICO = [
    (r'\b(no[- ]?jays|node[- ]?jays|nou[- ]?yeis|node[- ]?ye[ys]|node[- ]?js)\b', 'Node.js'),
    (r'\b(n[- ]?p[- ]?m)\b', 'NPM'),
    (r'\b(llaba|yaba)\b', 'Java'),
    (r'\b(open[- ]?j[- ]?d[- ]?k)\b', 'OpenJDK'),
    (r'\b(j[- ]?d[- ]?k)\b', 'JDK'),
    (r'\b(j[- ]?r[- ]?e)\b', 'JRE'),
    (r'\b(paiton|pit[oó]n|payton)\b', 'Python'),
    (r'\b(vscod[e]?|vs[- ]?code)\b', 'VS Code'),
    (r'\b(git[- ]?hub)\b', 'GitHub'),
    (r'\b(git[- ]?lab)\b', 'GitLab'),
    (r'\b(you[- ]?tube)\b', 'YouTube'),
    (r'\b(chat[- ]?g[- ]?p[- ]?t|chatgpt)\b', 'ChatGPT'),
    (r'\b(postgre[s]?[- ]?sql|posgres|postgre)\b', 'PostgreSQL'),
    (r'\b(maria[- ]?d[- ]?b)\b', 'MariaDB'),
    (r'\b(my[- ]?sql|maisenku?el)\b', 'MySQL'),
    (r'\b(redis)\b', 'Redis'),
    (r'\b(word[- ]?press)\b', 'WordPress'),
    (r'\b(fast[- ]?panel)\b', 'FastPanel'),
    (r'\b(cool[- ]?i?fy)\b', 'Coolify'),
    (r'\b(dok[e]?r|doker)\b', 'Docker'),
    (r'\b(vps)[- ]?([12345])\b', r'VPS-\2'),
    (r'\b(vps)\b', 'VPS'),
    (r'\b(power[- ]?shell|pauershel)\b', 'PowerShell'),
    (r'\b(wi[- ]?fi|uaifai)\b', 'Wi-Fi'),
    (r'\b(blue[- ]?tooth|blutut)\b', 'Bluetooth'),
    (r'\b(r[- ]?t[- ]?x)\s*(\d{3,4})\b', r'RTX \2'),
    (r'\b(ge[- ]?force)\b', 'GeForce'),
    (r'\b(v[- ]?ram)\b', 'VRAM'),
    (r'\b(c[- ]?u[- ]?d[- ]?a)\b', 'CUDA'),
    (r'\b(cu[- ]?d[- ]?n[- ]?n)\b', 'cuDNN'),
    (r'\b(ol[- ]?lama)\b', 'Ollama'),
    (r'\b(u[- ]?v)\b', 'uv'),
    (r'\b(brotli)\b', 'Brotli'),
]

def corregir_terminos_tecnicos(texto):
    """Corrige transliteraciones fonéticas erróneas de términos en inglés y tecnología."""
    if not texto:
        return ""
    t = texto
    for patron, reemplazo in DICCIONARIO_TECNOLOGICO:
        t = re.sub(patron, reemplazo, t, flags=re.IGNORECASE)
    return t

def formatear_puntuacion_dictado(texto):
    """
    Convierte palabras de puntuación habladas en sus símbolos ortográficos correspondientes,
    corrige términos tecnológicos comunes, ajusta espaciados y capitaliza el inicio.
    """
    if not texto:
        return ""
    t = corregir_terminos_tecnicos(texto.strip())
    reemplazos = [
        (r'\bpunto y aparte\b', '.\n\n'),
        (r'\bnueva l[ií]nea\b', '\n'),
        (r'\bnuevo p[aá]rrafo\b', '\n\n'),
        (r'\bpunto y coma\b', ';'),
        (r'\bdos puntos\b', ':'),
        (r'\bpunto seguido\b', '.'),
        (r'\bpuntos suspensivos\b', '...'),
        (r'\bcoma\b', ','),
        (r'\bpunto\b', '.'),
        (r'\bsigno de interrogaci[oó]n\b', '?'),
        (r'\bcerrar interrogaci[oó]n\b', '?'),
        (r'\babrir interrogaci[oó]n\b', '¿'),
        (r'\bsigno de admiraci[oó]n\b', '!'),
        (r'\bsigno de exclamaci[oó]n\b', '!'),
        (r'\bcerrar admiraci[oó]n\b', '!'),
        (r'\bcerrar exclamaci[oó]n\b', '!'),
        (r'\babrir admiraci[oó]n\b', '¡'),
        (r'\babrir exclamaci[oó]n\b', '¡'),
        (r'\babrir comillas\b', '"'),
        (r'\bcerrar comillas\b', '"'),
    ]
    for patron, reemplazo in reemplazos:
        t = re.sub(patron, reemplazo, t, flags=re.IGNORECASE)

    # Limpiar espacios antes de signos
    t = re.sub(r'\s+([,.:;?!])', r'\1', t)
    # Espacio tras signo si no viene seguido de espacio, salto de línea o número
    t = re.sub(r'([,.:;?!])([^\s\n\d"¿¡])', r'\1 \2', t)
    # Limpiar espacio tras signos de apertura
    t = re.sub(r'([¿¡])\s+', r'\1', t)

    if t:
        t = t[0].upper() + t[1:]
    return t

def ejecutar_comando(frase_reconocida):
    """Interpreta la frase y ejecuta la acción en Windows o consulta a Ollama."""
    try:
        import importlib
        importlib.reload(acciones)
    except Exception:
        pass
    t_original = normalizar(frase_reconocida)
    if not t_original:
        return

    user_name = config.get("user_name", "Jimmy")
    nickname = config.get("user_nickname", "Mochi")
    asistente_nombre = config.get("assistant_name", "Biktus")
    apodo = nickname if random.random() < 0.35 else user_name

    # Limpiar si el usuario se dirigió al asistente por su nombre:
    # "biktus", "victus", "oye biktus", "hey biktus", "hola biktus", etc.
    t = re.sub(r'^(oye |hey |hola )?(biktus|victus|viktus|bictus|asistente)\b[ ,]*', '', t_original).strip()

    # Si sólo dijo el nombre o un saludo genérico:
    if not t or t in ["hola", "buenas", "buenos dias", "buenos días", "buenas tardes", "buenas noches", "saludos", "hey", "hello"]:
        saludo = generar_saludo_dinamico()
        hablar(saludo)
        return

    print(f"\n🎯 Comando detectado: \"{frase_reconocida}\" (Acción: \"{t}\")")

    global modo_dictado_continuo

    # --- CONTROL DE MODO TRANSCRIPCIÓN / DICTADO CONTINUO ---
    if any(p in t for p in ["activar modo dictado", "activar dictado", "modo dictado", "activar transcripcion", "activar transcripción", "modo transcripcion", "modo transcripción"]):
        modo_dictado_continuo = True
        hablar("Modo transcripción activado. Todo lo que digas se insertará en el cursor.")
        return

    if any(p in t for p in ["desactivar modo dictado", "desactivar dictado", "salir de dictado", "desactivar transcripcion", "desactivar transcripción", "salir de transcripcion"]):
        modo_dictado_continuo = False
        hablar("Modo transcripción desactivado.")
        return

    # Si está en modo dictado continuo activo, todo lo que se hable se inserta en el cursor
    if modo_dictado_continuo:
        texto_formateado = formatear_puntuacion_dictado(frase_reconocida)
        logger.info(f"✍️ [Modo Continuo] Insertando en cursor: \"{texto_formateado}\"")
        acciones.escribir_texto_en_cursor(texto_formateado, hwnd_destino=active_target_hwnd)
        return

    # --- DICTADO POR COMANDO DE VOZ PUNTUAL ---
    # Ejemplos: "escribe: hola mundo", "escribe hola mundo", "dicta texto: ...", "transcribe: ...", "escribe aquí: ..."
    patron_dictado = re.match(
        r'^(?:por favor )?(?:biktus |victus |oye biktus )?(escribe|escribir|dicta|dictar|transcribe|transcribir|inserta|insertar|tipea|tipear)\b(?:\s+(aqui|aquí))?[:\s]*(.*)$',
        t_original,
        flags=re.IGNORECASE
    )
    if patron_dictado:
        hacer_clic = bool(patron_dictado.group(2))
        contenido = patron_dictado.group(3).strip()
        if contenido:
            texto_formateado = formatear_puntuacion_dictado(contenido)
            logger.info(f"✍️ Dictando al cursor ({'con clic' if hacer_clic else 'en foco'}): \"{texto_formateado}\"")
            acciones.escribir_texto_en_cursor(texto_formateado, hacer_clic_primero=hacer_clic, hwnd_destino=active_target_hwnd)
            return

    # --- IDENTIDAD / PREGUNTAS PERSONALES ---
    if any(p in t for p in ["quien eres", "quién eres", "como te llamas", "cómo te llamas", "tu nombre"]):
        hablar(f"Soy {asistente_nombre}, tu asistente de cabecera en esta laptop Victus. Y tú eres {user_name}, mi piloto estrella, aunque sé que de cariño te dicen {nickname}. ¡Todo ready a tu servicio!")
        return

    if any(p in t for p in ["quien soy", "quién soy", "como me llamo", "cómo me llamo", "mi nombre", "como me dicen", "cómo me dicen"]):
        hablar(f"Tú eres {user_name}, el dueño y señor de esta máquina; aunque para la familia eres {nickname}. ¡Un gusto siempre!")
        return

    if any(p in t for p in ["como estas", "cómo estás", "que tal", "qué tal", "todo bien", "all good"]):
        respuestas_estado = [
            f"Todo super bien, {apodo}! Con la RTX y el sistema al 100%. ¿Qué hay para hacer?",
            f"All good por acá, {apodo}! Listo y esperando tus comandos.",
            f"Excelente, {apodo}, ready para trabajar o jugar lo que quieras."
        ]
        hablar(random.choice(respuestas_estado))
        return

    # --- CAMBIO DE MODO DE CEREBRO (LOCAL vs NUBE / GEMINI) ---
    if any(p in t for p in ["modo nube", "cambiar a modo nube", "cambia a modo nube", "activa modo nube", "activar modo nube", "modo gemini", "usar gemini", "usa gemini", "conectar a la nube"]):
        api_key = config.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY") or ""
        config["brain_mode"] = "cloud"
        guardar_config()
        if api_key.strip():
            hablar(f"All right, {apodo}! Modo nube activado. Cerebro conectado a Gemini.")
        else:
            hablar(f"Modo nube activado, {apodo}, pero recuerda ingresar tu API key de Gemini en config.json para poder responderte.")
        return

    if any(p in t for p in ["modo local", "cambiar a modo local", "cambia a modo local", "activa modo local", "activar modo local", "modo ollama", "usar ollama", "usa ollama", "modo offline"]):
        config["brain_mode"] = "local"
        guardar_config()
        hablar(f"Todo ready, {apodo}! Modo local activado. Procesando todo 100% offline con tu RTX y Ollama.")
        return

    if any(p in t for p in ["que modo estas", "qué modo estás", "en que modo estas", "en qué modo estás", "modo actual"]):
        modo = config.get("brain_mode", "local")
        if modo == "cloud":
            hablar(f"Actualmente estoy en modo nube, potenciado por Gemini, {apodo}.")
        else:
            hablar(f"Actualmente estoy en modo local offline, funcionando con Ollama y tu RTX, {apodo}.")
        return

    # --- ACCIONES DEL SISTEMA ---
    # Salir del asistente
    if any(p in t for p in ["cerrar asistente", "apagar asistente", "salir del asistente", "apaga el asistente"]):
        hablar("Hasta pronto.")
        time.sleep(1)
        os._exit(0)

    # Menú Inicio
    if any(p in t for p in ["abrir inicio", "abre inicio", "menu inicio", "menú inicio", "abre el menu", "abrir el menu", "abrir menú", "menu de inicio", "menú de inicio", "abre el inicio", "abrir el inicio", "inicio"]):
        msg = acciones.abrir_inicio()
        hablar("Menú de inicio")
        return

    # Antigravity (Detección inteligente entre 2.0 e IDE tanto para abrir como para cerrar)
    if "antigravity" in t or "antigravedad" in t or (("ide" in t.split() or "id" in t.split()) and ("abrir" in t or "abre" in t or "cierra" in t or "cerrar" in t or "sierra" in t)):
        cerrar = es_intencion_cerrar(t)
        es_ide = any(w in t.split() for w in ["ide", "id"]) or any(w in t for w in ["i d e", "i-d-e", "i d"])
        if es_ide:
            if cerrar:
                acciones.cerrar_antigravity_ide()
                hablar(f"Cerrando Antigravity IDE, {apodo}.")
            else:
                acciones.abrir_antigravity_ide()
                hablar("Abriendo Antigravity IDE")
            return
        else:
            if cerrar:
                acciones.cerrar_antigravity()
                hablar(f"Cerrando Antigravity 2.0, {apodo}.")
            else:
                acciones.abrir_antigravity()
                hablar("Abriendo Antigravity 2.0")
            return

    # Calculadora
    if "calculadora" in t:
        if es_intencion_cerrar(t):
            acciones.cerrar_calculadora()
            hablar("Calculadora cerrada.")
        else:
            acciones.abrir_calculadora()
            hablar("Abriendo calculadora.")
        return

    # Bloc de notas
    if "bloc de notas" in t or "notepad" in t:
        if es_intencion_cerrar(t):
            acciones.cerrar_bloc_notas()
            hablar("Bloc de notas cerrado.")
        else:
            acciones.abrir_bloc_notas()
            hablar("Abriendo bloc de notas.")
        return

    # Explorador de archivos
    if any(p in t for p in ["explorador de archivos", "abrir explorador", "abre explorador", "cierra explorador", "cerrar explorador", "sierra explorador"]):
        if es_intencion_cerrar(t):
            acciones.cerrar_ventana()
            hablar("Explorador cerrado.")
        else:
            acciones.abrir_explorador()
            hablar("Abriendo el explorador.")
        return

    # Administrador de tareas
    if "administrador de tareas" in t or ("tareas" in t and ("abrir" in t or "abre" in t or es_intencion_cerrar(t))):
        if es_intencion_cerrar(t):
            acciones.cerrar_administrador_tareas()
            hablar("Administrador de tareas cerrado.")
        else:
            acciones.abrir_administrador_tareas()
            hablar("Abriendo administrador de tareas.")
        return

    # Configuración de Windows
    if any(p in t for p in ["abrir configuracion", "abrir configuración", "ajustes", "cierra configuracion", "cerrar configuracion"]):
        if es_intencion_cerrar(t):
            acciones.cerrar_ventana()
            hablar("Configuración cerrada.")
        else:
            acciones.abrir_configuracion()
            hablar("Abriendo configuración.")
        return

    # Cerrar ventana activa o cerrar aplicación
    if any(p in t for p in ["cerrar ventana", "cierra la ventana", "cierra esta ventana", "cerrar la ventana", "cerrar aplicacion", "cerrar aplicación", "cierra la aplicacion", "cierra la aplicación", "cerrar programa", "cierra el programa", "cerrar app", "cierra la app"]) or t in ["cierra", "cerrar", "sierra", "cierralo", "ciérralo", "cierrala", "ciérrala"]:
        acciones.cerrar_ventana()
        hablar("Ventana cerrada.")
        return

    # Cerrar pestaña activa (Ctrl + W)
    if any(p in t for p in ["cerrar pestaña", "cierra la pestaña", "cierra esta pestaña", "cerrar la pestaña", "cerrar pestana", "cierra la pestana"]):
        acciones.cerrar_pestana()
        hablar("Pestaña cerrada.")
        return

    # Minimizar todo / Escritorio (Win + D)
    if any(p in t for p in ["minimizar todo", "minimiza todo", "minimizar ventanas", "mostrar escritorio", "ir al escritorio", "ver escritorio", "minimizar"]):
        acciones.minimizar_todo()
        hablar("Escritorio mostrado.")
        return

    # --- CONTROL DE VOLUMEN ---
    if "subir volumen" in t or "sube el volumen" in t:
        acciones.subir_volumen()
        hablar("Volumen aumentado")
        return

    if "bajar volumen" in t or "baja el volumen" in t:
        acciones.bajar_volumen()
        hablar("Volumen reducido")
        return

    if "silenciar" in t or "silencio" in t or "mutear" in t:
        acciones.silenciar_volumen()
        hablar("Silencio")
        return

    # --- NAVEGACIÓN Y NAVEGADORES ---
    if any(p in t for p in ["firefox", "mozilla"]):
        if es_intencion_cerrar(t):
            acciones.cerrar_firefox()
            hablar(f"Cerrando Firefox, {apodo}.")
        else:
            acciones.abrir_firefox()
            hablar(f"Abriendo Firefox, {apodo}.")
        return

    if "chrome" in t:
        if es_intencion_cerrar(t):
            acciones.cerrar_chrome()
            hablar(f"Cerrando Chrome, {apodo}.")
        else:
            acciones.abrir_chrome()
            hablar(f"Abriendo Chrome, {apodo}.")
        return

    if any(p in t for p in ["edge", "microsoft edge"]):
        if es_intencion_cerrar(t):
            acciones.cerrar_edge()
            hablar(f"Cerrando Edge, {apodo}.")
        else:
            acciones.abrir_edge()
            hablar(f"Abriendo Edge, {apodo}.")
        return

    if any(p in t for p in ["el navegador", "navegador web", "abrir navegador", "cerrar navegador", "cierra el navegador"]):
        if es_intencion_cerrar(t):
            acciones.cerrar_navegador()
            hablar("Navegador cerrado.")
        else:
            acciones.abrir_navegador()
            hablar("Abriendo el navegador.")
        return

    if "abrir youtube" in t or "abre youtube" in t or t == "youtube":
        acciones.abrir_web("youtube.com", "YouTube")
        hablar("Abriendo YouTube")
        return

    if "abrir google" in t or "abre google" in t or t == "google":
        acciones.abrir_web("google.com", "Google")
        hablar("Abriendo Google")
        return

    if "abrir github" in t or "abre github" in t:
        acciones.abrir_web("github.com", "GitHub")
        hablar("Abriendo GitHub")
        return

    if t.startswith("busca en google ") or t.startswith("buscar en google "):
        query = t.replace("busca en google ", "").replace("buscar en google ", "")
        acciones.buscar_en_google(query)
        hablar(f"Buscando {query} en Google")
        return

    if t.startswith("busca en youtube ") or t.startswith("buscar en youtube "):
        query = t.replace("busca en youtube ", "").replace("buscar en youtube ", "")
        acciones.buscar_en_youtube(query)
        hablar(f"Buscando {query} en YouTube")
        return

    if t.startswith("abrir ") and ("." in t or "pagina" in t):
        sitio = t.replace("abrir ", "").replace("pagina ", "").strip()
        acciones.abrir_web(sitio)
        hablar(f"Abriendo {sitio}")
        return

    # --- FECHA Y HORA ---
    if any(p in t for p in ["que hora es", "qué hora es", "dime la hora", "la hora"]):
        hora_str = acciones.obtener_hora()
        hablar(hora_str)
        return

    if any(p in t for p in ["que dia es", "qué día es", "que fecha es", "qué fecha es", "fecha de hoy"]):
        fecha_str = acciones.obtener_fecha()
        hablar(fecha_str)
        return

    # --- ENRUTAR AL CEREBRO ACTIVO (Gemini en nube u Ollama en local) ---
    print("💡 No es un comando de sistema. Enviando consulta al cerebro activo...")
    respuesta = consultar_cerebro(frase_reconocida)
    print(f"🤖 Respuesta ({config.get('brain_mode', 'local')}):\n{respuesta}\n")
    hablar(respuesta)

# 5. Pipeline de Transcripción
def procesar_audio(es_dictado=False):
    global audio_frames
    with recording_lock:
        if not audio_frames:
            return
        audio_data = np.concatenate(audio_frames, axis=0).flatten()
        audio_frames = []

    # Verificar si hay suficiente duración (> 0.25s)
    duracion = len(audio_data) / sample_rate
    if duracion < 0.25:
        if hud is not None:
            hud.ocultar()
        logger.info("⚠️ Grabación demasiado corta.")
        return

    # Normalización dinámica de volumen: compensa micrófonos integrados de laptop con baja ganancia o lejanía
    max_val = np.max(np.abs(audio_data))
    if max_val > 1e-4:
        audio_data = (audio_data / max_val) * 0.95

    prompt_inicial = (
        "Antigravity, Antigravity IDE, Biktus, Victus, Jimmy, Mochi, Firefox, Chrome, Edge, "
        "Node.js, NodeJS, JavaScript, TypeScript, Python, Java, OpenJDK, JDK, Docker, GitHub, Git, NPM, "
        "VPS-1, VPS-2, Linux, Ubuntu, Debian, FastPanel, Coolify, WordPress, PostgreSQL, MySQL, MariaDB, Redis, "
        "Ollama, Whisper, CUDA, cuDNN, RTX 4060, VRAM, API, REST, JSON, YAML, HTML, CSS, PowerShell, Bash, "
        "abrir, abre, cerrar, cierra, navegador, inicio, explorador, calculadora, bloc de notas, "
        "volumen, YouTube, Google, ventana, pestaña, punto, coma, dos puntos, punto y coma, "
        "punto y aparte, nueva línea, enter, escribe, dictado, transcribir."
    )

    logger.info(f"🧠 Transcribiendo con Whisper ({duracion:.1f}s de audio)...")
    t0 = time.time()
    texto = ""
    try:
        segments, info = whisper_model.transcribe(
            audio_data,
            language=config.get("language", "es"),
            beam_size=2,
            vad_filter=True,
            vad_parameters=dict(threshold=0.35, min_silence_duration_ms=300, speech_pad_ms=300),
            initial_prompt=prompt_inicial
        )
        texto = " ".join([seg.text for seg in segments]).strip()
        elapsed = time.time() - t0
        logger.info(f"⚡ Transcripción ({elapsed:.2f}s en GPU): \"{texto}\"")
    except Exception as e:
        logger.warning(f"⚠️ Error al transcribir en GPU ({e}). Recurriendo a CPU...")
        try:
            cpu_model = WhisperModel(config.get("whisper_model", "small"), device="cpu", compute_type="int8")
            segments, info = cpu_model.transcribe(
                audio_data,
                language=config.get("language", "es"),
                beam_size=1,
                vad_filter=True,
                vad_parameters=dict(threshold=0.35, min_silence_duration_ms=300, speech_pad_ms=300),
                initial_prompt=prompt_inicial
            )
            texto = " ".join([seg.text for seg in segments]).strip()
            logger.info(f"⚡ Transcripción en CPU: \"{texto}\"")
        except Exception as err2:
            logger.error(f"❌ Error al transcribir: {err2}")
            if hud is not None:
                hud.ocultar()
            return

    if not texto:
        if hud is not None:
            hud.ocultar()
        logger.info("🔇 No se detectaron palabras audibles.")
        return

    try:
        if es_dictado:
            texto_formateado = formatear_puntuacion_dictado(texto)
            logger.info(f"✍️ [Dictado Directo F9] Insertando: \"{texto_formateado}\"")
            acciones.escribir_texto_en_cursor(texto_formateado, hwnd_destino=active_target_hwnd)
        else:
            ejecutar_comando(texto)
    finally:
        if hud is not None:
            hud.ocultar()

# 6. Manejador de Teclas (Push-to-Talk)
hotkey_cfg = config.get("hotkey", "f8")
if isinstance(hotkey_cfg, list):
    command_hotkeys = [h.lower() for h in hotkey_cfg]
else:
    command_hotkeys = [str(hotkey_cfg).lower(), "ctrl_r"]

dictation_hotkey_cfg = config.get("dictation_hotkey", "f9")
if isinstance(dictation_hotkey_cfg, list):
    dictation_hotkeys = [h.lower() for h in dictation_hotkey_cfg]
else:
    dictation_hotkeys = [str(dictation_hotkey_cfg).lower()]

all_hotkeys = set(command_hotkeys + dictation_hotkeys)

active_key = None
current_is_dictation = False
active_target_hwnd = None

def mapear_tecla(key):
    try:
        if hasattr(key, "name"):
            return key.name.lower()
        if hasattr(key, "char") and key.char:
            return key.char.lower()
    except Exception:
        pass
    return str(key).lower()

def on_press(key):
    try:
        global is_recording, active_key, current_is_dictation, active_target_hwnd
        k = mapear_tecla(key)
        if k in all_hotkeys:
            if not is_recording:
                active_key = k

                # Capturar ventana con foco original para asegurar que el texto pegado no se pierda
                cur_fg = user32.GetForegroundWindow()
                if hud and hud.root:
                    try:
                        hud_hwnd = user32.GetParent(hud.root.winfo_id()) or hud.root.winfo_id()
                        if cur_fg != hud_hwnd and cur_fg != 0:
                            active_target_hwnd = cur_fg
                    except Exception:
                        active_target_hwnd = cur_fg
                else:
                    active_target_hwnd = cur_fg
                es_tecla_dictado = k in dictation_hotkeys
                current_is_dictation = es_tecla_dictado or modo_dictado_continuo
                with recording_lock:
                    audio_frames.clear()
                    is_recording = True

                if hud is not None:
                    hud.iniciar_grabacion("dictado" if current_is_dictation else "asistente")

                if current_is_dictation:
                    sonar_pitido(1200, 30)
                    logger.info(f"\n✍️ [TRANSCRIBIENDO AL CURSOR...] (Habla ahora, suelta [{k.upper()}] al terminar)")
                else:
                    sonar_pitido(1000, 30)
                    logger.info(f"\n🔴 [GRABANDO ASISTENTE...] (Habla ahora, suelta [{k.upper()}] al terminar)")
    except Exception as err:
        logger.error(f"Error en on_press: {err}")

def on_release(key):
    try:
        global is_recording, active_key, current_is_dictation
        k = mapear_tecla(key)
        if is_recording and (k == active_key or k in all_hotkeys or active_key is None):
            fue_dictado = current_is_dictation
            active_key = None
            with recording_lock:
                is_recording = False

            if hud is not None:
                hud.indicar_procesando()

            if fue_dictado:
                sonar_pitido(750, 30)
                logger.info("⏹️ [FIN DE DICTADO] Insertando en cursor...")
            else:
                sonar_pitido(600, 30)
                logger.info("⏹️ [FIN DE GRABACIÓN] Procesando en GPU...")

            threading.Thread(target=procesar_audio, args=(fue_dictado,), daemon=True).start()
    except Exception as err:
        logger.error(f"Error en on_release: {err}")

def main():
    print("\n" + "-" * 60)
    print("👉 MODOS ACTIVADOS: Push-to-Talk")
    print("   🎙️ ASISTENTE (Comandos / Preguntas): Mantén [F8]  o  [Ctrl DERECHA]")
    print("   ✍️ DICTADO DIRECTO (Insertar al cursor): Mantén [F9]")
    print("   • En laptops, si F8 o F9 tienen funciones multimedia, usa Fn o Ctrl Derecha.")
    print("   • Por voz con F8 también puedes decir: 'Escribe [texto]' o 'Activar modo dictado'.")
    print("   • Para probar sin hablar, escribe un comando abajo y pulsa Enter.")
    print("-" * 60 + "\n")

    # Iniciar Listener de teclado en hilo secundario
    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()

    # Saludo de bienvenida por voz
    hablar("Asistente de voz listo. Pulsa F8 para comandos o F9 para dictar directamente.")

    try:
        while True:
            try:
                line = input()
                if line.strip():
                    ejecutar_comando(line.strip())
            except EOFError:
                break
    except KeyboardInterrupt:
        print("\n👋 Cerrando asistente...")
    finally:
        audio_stream.stop()
        audio_stream.close()
        listener.stop()

if __name__ == "__main__":
    main()
