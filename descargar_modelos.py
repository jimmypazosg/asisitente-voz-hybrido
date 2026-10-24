"""Script utilitario para descargar los pesos neuronales de Kokoro TTS (offline).

Descarga:
  1. kokoro-v1.0.onnx (~326 MB)
  2. voices-v1.0.bin (~28 MB)

Los archivos se guardan en el directorio `models/kokoro/`.
"""

import os
import sys
import urllib.request

MODELS = [
    {
        "filename": "kokoro-v1.0.onnx",
        "url": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx",
        "size_mb": 326
    },
    {
        "filename": "voices-v1.0.bin",
        "url": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin",
        "size_mb": 28
    }
]

def reporte_progreso(bloques_transferidos, tamano_bloque, tamano_total):
    if tamano_total > 0:
        porcentaje = min(100.0, (bloques_transferidos * tamano_bloque / tamano_total) * 100)
        mb_descargados = (bloques_transferidos * tamano_bloque) / (1024 * 1024)
        mb_totales = tamano_total / (1024 * 1024)
        sys.stdout.write(f"\r  -> Progreso: {porcentaje:.1f}% ({mb_descargados:.1f} MB / {mb_totales:.1f} MB)")
        sys.stdout.flush()

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    destino_dir = os.path.join(base_dir, "models", "kokoro")
    os.makedirs(destino_dir, exist_ok=True)

    print("=" * 60)
    print("  DESCARGADOR DE MODELOS NEURONALES KOKORO TTS")
    print("=" * 60)
    print(f"Directorio de destino: {destino_dir}\n")

    for m in MODELS:
        ruta_archivo = os.path.join(destino_dir, m["filename"])
        if os.path.exists(ruta_archivo) and os.path.getsize(ruta_archivo) > 1024 * 1024:
            print(f"[OK] {m['filename']} ya existe ({os.path.getsize(ruta_archivo)/(1024*1024):.1f} MB). Saltando.")
            continue

        print(f"[DESCARGANDO] {m['filename']} (~{m['size_mb']} MB)...")
        print(f"  Fuente: {m['url']}")
        try:
            # Añadir cabecera User-Agent para evitar posibles bloqueos 403 de GitHub
            opener = urllib.request.build_opener()
            opener.addheaders = [("User-Agent", "Mozilla/5.0")]
            urllib.request.install_opener(opener)

            urllib.request.urlretrieve(m["url"], ruta_archivo, reporthook=reporte_progreso)
            print("\n  -> Descarga completada con éxito.\n")
        except Exception as e:
            print(f"\n[ERROR] Falló la descarga de {m['filename']}: {e}")
            print(f"  Puedes descargarlo manualmente desde: {m['url']}")
            print(f"  y colocarlo en: {ruta_archivo}\n")

    print("=" * 60)
    print("  Proceso finalizado. Modelos listos para su uso.")
    print("=" * 60)

if __name__ == "__main__":
    main()
