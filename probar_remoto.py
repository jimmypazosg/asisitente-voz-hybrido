"""
Script de pruebas y control en remoto para el Asistente de Voz.
Permite probar el enrutador de comandos, Ollama y el sintetizador de voz
sin depender del micrófono físico ni de la tecla física F8 (ideal para SSH o escritorio remoto).
"""

import sys
import os

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

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

import argparse
from asistente import ejecutar_comando, consultar_ollama, hablar

def main():
    parser = argparse.ArgumentParser(description="Pruebas remotas del asistente de voz")
    parser.add_argument("-c", "--comando", type=str, help="Ejecutar un comando directamente (ej: 'abrir bloc de notas', 'que hora es')")
    parser.add_argument("-p", "--pregunta", type=str, help="Hacer una pregunta directa a Ollama")
    parser.add_argument("-t", "--tts", type=str, help="Probar síntesis de voz con un texto específico")
    args = parser.parse_args()

    if args.comando:
        print(f"\n[REMOTO] Ejecutando comando: '{args.comando}'")
        ejecutar_comando(args.comando)
        return

    if args.pregunta:
        print(f"\n[REMOTO] Preguntando a Ollama: '{args.pregunta}'")
        resp = consultar_ollama(args.pregunta)
        print(f"Respuesta: {resp}")
        hablar(resp)
        return

    if args.tts:
        print(f"\n[REMOTO] Probando síntesis de voz: '{args.tts}'")
        hablar(args.tts)
        return

    # Modo interactivo si no se pasan argumentos
    print("\n" + "=" * 60)
    print("📡 MODO DE PRUEBAS REMOTAS DEL ASISTENTE (Sin Micrófono)")
    print("=" * 60)
    print("Escribe un comando o pregunta y presiona Enter.")
    print("Escribe 'salir' para terminar.\n")

    while True:
        try:
            line = input("Remoto > ").strip()
            if not line:
                continue
            if line.lower() in ["salir", "exit", "quit"]:
                break
            ejecutar_comando(line)
        except (KeyboardInterrupt, EOFError):
            break
    print("\nSesión remota finalizada.")

if __name__ == "__main__":
    main()
