import ctypes
import os
import subprocess
import threading
import time
import urllib.parse
import webbrowser
from datetime import datetime
import win32clipboard
import win32com.client
import win32con

from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
try:
    user32.AllowSetForegroundWindow(-1)
except Exception:
    pass

def obtener_hora():
    ahora = datetime.now()
    return f"Son las {ahora.strftime('%H y %M')} minutos."

def obtener_fecha():
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    ahora = datetime.now()
    dia_semana = dias[ahora.weekday()]
    mes = meses[ahora.month - 1]
    return f"Hoy es {dia_semana}, {ahora.day} de {mes} de {ahora.year}."

# Códigos de teclas virtuales de Windows
VK_LWIN = 0x5B
VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_ESCAPE = 0x1B
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
KEYEVENTF_KEYUP = 0x0002

LOCAL_APP_DATA = os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
ANTIGRAVITY_2_PATH = os.path.join(LOCAL_APP_DATA, "Programs", "antigravity", "Antigravity.exe")
ANTIGRAVITY_IDE_PATH = os.path.join(LOCAL_APP_DATA, "Programs", "Antigravity IDE", "Antigravity IDE.exe")

def presionar_tecla(vk_code):
    """Simula pulsar y soltar una tecla virtual."""
    user32.keybd_event(vk_code, 0, 0, 0)
    user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)

def abrir_inicio():
    """Abre o cierra el menú de inicio de Windows en primer plano."""
    presionar_tecla(VK_LWIN)
    return "Menú de inicio activado."

def _obtener_nombre_proceso(pid):
    """Obtiene el nombre completo o ejecutable de un proceso por su PID."""
    h_proc = kernel32.OpenProcess(0x1000, False, pid) # PROCESS_QUERY_LIMITED_INFORMATION
    if not h_proc:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(h_proc, 0, buf, ctypes.byref(size)):
            return buf.value
        return ""
    finally:
        kernel32.CloseHandle(h_proc)

def buscar_ventana(nombres_exe=None, fragmentos_titulo=None):
    """
    Busca la ventana principal activa y visible en el escritorio que coincida con
    el nombre del ejecutable o fragmento del título.
    """
    nombres_exe_limpios = [n.lower() for n in nombres_exe] if nombres_exe else []
    fragmentos_limpios = [f.lower() for f in fragmentos_titulo] if fragmentos_titulo else []
    candidatas = []

    def enum_cb(hwnd, _):
        if not user32.IsWindow(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            titulo = buf.value
            titulo_low = titulo.lower()

            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            ruta_exe = _obtener_nombre_proceso(pid.value)
            nombre_exe = os.path.basename(ruta_exe).lower() if ruta_exe else ""

            coincide_exe = any(nombre_exe == n or nombre_exe.endswith(n) for n in nombres_exe_limpios) if nombres_exe_limpios else False
            coincide_tit = any(f in titulo_low for f in fragmentos_limpios) if fragmentos_limpios else False

            if coincide_exe or coincide_tit:
                es_visible = bool(user32.IsWindowVisible(hwnd))
                es_minimizada = bool(user32.IsIconic(hwnd))
                if es_visible or es_minimizada:
                    if titulo not in ["MSCTFIME UI", "Default IME"]:
                        candidatas.append((hwnd, pid.value, titulo, nombre_exe))
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    DESKTOP_READOBJECTS = 0x0001
    DESKTOP_ENUMERATE = 0x0040
    hdesk = user32.OpenInputDesktop(0, False, DESKTOP_READOBJECTS | DESKTOP_ENUMERATE)
    if hdesk:
        try:
            user32.EnumDesktopWindows(hdesk, WNDENUMPROC(enum_cb), 0)
        finally:
            user32.CloseDesktop(hdesk)

    if not candidatas:
        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)

    if candidatas:
        if nombres_exe_limpios:
            for item in candidatas:
                if any(item[3] == n for n in nombres_exe_limpios):
                    return item[0]
        return candidatas[0][0]

    return None

def forzar_primer_plano(hwnd):
    """
    Desbloquea el bloqueo de foco de Windows y fuerza a que la ventana indicada
    pase al frente absoluto de la pantalla, incluso por encima de otras aplicaciones.
    """
    if not hwnd or not user32.IsWindow(hwnd):
        return False

    # Asegurar que el hilo actual apunte al escritorio de entrada activo
    DESKTOP_READOBJECTS = 0x0001
    DESKTOP_ENUMERATE = 0x0040
    hdesk = user32.OpenInputDesktop(0, False, DESKTOP_READOBJECTS | DESKTOP_ENUMERATE)
    old_desk = user32.GetThreadDesktop(kernel32.GetCurrentThreadId())
    cambio_desktop = False
    if hdesk:
        try:
            if user32.SetThreadDesktop(hdesk):
                cambio_desktop = True
        except Exception:
            pass

    try:
        # 1. Configurar tiempo de bloqueo de primer plano a 0
        SPI_SETFOREGROUNDLOCKTIMEOUT = 0x2001
        SPIF_SENDCHANGE = 0x0002
        user32.SystemParametersInfoW(SPI_SETFOREGROUNDLOCKTIMEOUT, 0, ctypes.c_void_p(0), SPIF_SENDCHANGE)
        try:
            user32.LockSetForegroundWindow(2) # LSFW_UNLOCK
        except Exception:
            pass

        # 2. Restaurar si está minimizada o mostrar si está oculta
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9) # SW_RESTORE
        else:
            user32.ShowWindow(hwnd, 5) # SW_SHOW

        # 3. Simular pulsación de tecla ALT para engañar al gestor de ventanas de Windows
        VK_MENU = 0x12
        KEYEVENTF_KEYUP = 0x0002
        user32.keybd_event(VK_MENU, 0, 0, 0)
        user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)

        # 4. AttachThreadInput para heredar permisos de foco del hilo en primer plano
        fg_hwnd = user32.GetForegroundWindow()
        cur_tid = kernel32.GetCurrentThreadId()
        fg_tid = user32.GetWindowThreadProcessId(fg_hwnd, None) if fg_hwnd else 0
        target_tid = user32.GetWindowThreadProcessId(hwnd, None)

        attached_fg = False
        attached_cur = False
        try:
            if fg_tid and fg_tid != target_tid:
                user32.AttachThreadInput(fg_tid, target_tid, True)
                attached_fg = True
            if cur_tid and cur_tid != target_tid:
                user32.AttachThreadInput(cur_tid, target_tid, True)
                attached_cur = True

            try:
                user32.AllowSetForegroundWindow(-1)
            except Exception:
                pass

            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
            user32.SetFocus(hwnd)
        finally:
            if attached_cur:
                user32.AttachThreadInput(cur_tid, target_tid, False)
            if attached_fg:
                user32.AttachThreadInput(fg_tid, target_tid, False)
    finally:
        if cambio_desktop and old_desk:
            user32.SetThreadDesktop(old_desk)
        if hdesk:
            user32.CloseDesktop(hdesk)

    return True

def activar_o_lanzar(nombres_exe, ruta_ejecutable, fragmentos_titulo=None, timeout=3.5):
    """
    Si la ventana ya existe, la trae de inmediato al primer plano.
    Si no existe, ejecuta la aplicación y espera a que su ventana aparezca para traerla al frente.
    """
    hwnd = buscar_ventana(nombres_exe=nombres_exe, fragmentos_titulo=fragmentos_titulo)
    if hwnd:
        forzar_primer_plano(hwnd)
        return True

    try:
        if os.path.exists(ruta_ejecutable):
            subprocess.Popen([ruta_ejecutable], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(ruta_ejecutable, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        return False

    inicio = time.time()
    while time.time() - inicio < timeout:
        time.sleep(0.15)
        hwnd = buscar_ventana(nombres_exe=nombres_exe, fragmentos_titulo=fragmentos_titulo)
        if hwnd:
            forzar_primer_plano(hwnd)
            return True

    return False

def abrir_antigravity():
    """Inicia o pasa a primer plano Antigravity 2.0."""
    ruta = ANTIGRAVITY_2_PATH if os.path.exists(ANTIGRAVITY_2_PATH) else "antigravity"
    activar_o_lanzar(
        nombres_exe=["antigravity.exe"],
        ruta_ejecutable=ruta,
        fragmentos_titulo=None,
        timeout=3.5
    )
    return "Abriendo Antigravity 2.0."

def abrir_antigravity_ide():
    """Inicia o pasa a primer plano Antigravity IDE."""
    ruta = ANTIGRAVITY_IDE_PATH if os.path.exists(ANTIGRAVITY_IDE_PATH) else "antigravity-ide"
    activar_o_lanzar(
        nombres_exe=["antigravity ide.exe"],
        ruta_ejecutable=ruta,
        fragmentos_titulo=["antigravity ide"],
        timeout=3.5
    )
    return "Abriendo Antigravity IDE."

def cerrar_proceso(nombre_exe, nombre_amigable=None):
    """Cierra de forma efectiva todos los procesos asociados a un ejecutable."""
    nombre_amigable = nombre_amigable or nombre_exe
    try:
        subprocess.run(f'taskkill /IM "{nombre_exe}" /T', shell=True, capture_output=True, text=True)
        time.sleep(0.3)
        check = subprocess.run(f'tasklist /FI "IMAGENAME eq {nombre_exe}"', shell=True, capture_output=True, text=True)
        if nombre_exe.lower() in check.stdout.lower():
            subprocess.run(f'taskkill /F /IM "{nombre_exe}" /T', shell=True, capture_output=True, text=True)
        return f"{nombre_amigable} cerrado."
    except Exception as e:
        return f"Error al cerrar {nombre_amigable}: {e}"

def cerrar_antigravity():
    """Cierra Antigravity 2.0."""
    return cerrar_proceso("Antigravity.exe", "Antigravity 2.0")

def cerrar_antigravity_ide():
    """Cierra Antigravity IDE."""
    return cerrar_proceso("Antigravity IDE.exe", "Antigravity IDE")

def abrir_calculadora():
    """Abre la calculadora y la sitúa en primer plano."""
    activar_o_lanzar(
        nombres_exe=["calculatorapp.exe", "calc.exe"],
        ruta_ejecutable="calc",
        fragmentos_titulo=["calculadora", "calculator"],
        timeout=2.5
    )
    return "Abriendo calculadora."

def abrir_bloc_notas():
    """Abre el bloc de notas y lo sitúa en primer plano."""
    activar_o_lanzar(
        nombres_exe=["notepad.exe"],
        ruta_ejecutable="notepad",
        fragmentos_titulo=["bloc de notas", "notepad"],
        timeout=2.5
    )
    return "Abriendo bloc de notas."

def abrir_explorador():
    """Abre el explorador de archivos directamente en primer plano simulando Win + E."""
    user32.keybd_event(VK_LWIN, 0, 0, 0)
    user32.keybd_event(0x45, 0, 0, 0) # Tecla 'E'
    time.sleep(0.05)
    user32.keybd_event(0x45, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_LWIN, 0, KEYEVENTF_KEYUP, 0)
    return "Abriendo el explorador de archivos."

def abrir_administrador_tareas():
    """Abre el administrador de tareas en primer plano (Ctrl + Shift + Esc)."""
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(VK_SHIFT, 0, 0, 0)
    user32.keybd_event(VK_ESCAPE, 0, 0, 0)
    time.sleep(0.05)
    user32.keybd_event(VK_ESCAPE, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_SHIFT, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
    return "Abriendo el administrador de tareas."

def abrir_configuracion():
    """Abre configuración de Windows en primer plano (Win + I)."""
    user32.keybd_event(VK_LWIN, 0, 0, 0)
    user32.keybd_event(0x49, 0, 0, 0) # Tecla 'I'
    time.sleep(0.05)
    user32.keybd_event(0x49, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_LWIN, 0, KEYEVENTF_KEYUP, 0)
    return "Abriendo configuración de Windows."


def subir_volumen(veces=3):
    for _ in range(veces):
        presionar_tecla(VK_VOLUME_UP)
    return "Subiendo volumen."

def bajar_volumen(veces=3):
    for _ in range(veces):
        presionar_tecla(VK_VOLUME_DOWN)
    return "Bajando volumen."

def silenciar_volumen():
    presionar_tecla(VK_VOLUME_MUTE)
    return "Silencio activado o desactivado."

def abrir_firefox():
    """Abre Mozilla Firefox y lo trae al primer plano."""
    activar_o_lanzar(
        nombres_exe=["firefox.exe"],
        ruta_ejecutable="start firefox",
        fragmentos_titulo=["firefox", "mozilla"],
        timeout=3.0
    )
    return "Abriendo Firefox."

def abrir_chrome():
    """Abre Google Chrome y lo trae al primer plano."""
    activar_o_lanzar(
        nombres_exe=["chrome.exe"],
        ruta_ejecutable="start chrome",
        fragmentos_titulo=["chrome", "google"],
        timeout=3.0
    )
    return "Abriendo Chrome."

def abrir_edge():
    """Abre Microsoft Edge y lo trae al primer plano."""
    activar_o_lanzar(
        nombres_exe=["msedge.exe"],
        ruta_ejecutable="start msedge",
        fragmentos_titulo=["edge"],
        timeout=3.0
    )
    return "Abriendo Edge."

def abrir_navegador():
    webbrowser.open("https://www.google.com")
    return "Abriendo el navegador web."

def abrir_web(url, nombre_sitio=None):
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    webbrowser.open(url)
    return f"Abriendo {nombre_sitio or url}."

def buscar_en_google(consulta):
    url = f"https://www.google.com/search?q={urllib.parse.quote(consulta)}"
    webbrowser.open(url)
    return f"Buscando en Google: {consulta}."

def buscar_en_youtube(consulta):
    url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(consulta)}"
    webbrowser.open(url)
    return f"Buscando en YouTube: {consulta}."

def cerrar_calculadora():
    """Cierra la calculadora."""
    cerrar_proceso("CalculatorApp.exe", "Calculadora")
    cerrar_proceso("calc.exe", "Calculadora")
    return "Calculadora cerrada."

def cerrar_bloc_notas():
    """Cierra el bloc de notas."""
    return cerrar_proceso("Notepad.exe", "Bloc de notas")

def cerrar_firefox():
    """Cierra Mozilla Firefox."""
    return cerrar_proceso("firefox.exe", "Firefox")

def cerrar_chrome():
    """Cierra Google Chrome."""
    return cerrar_proceso("chrome.exe", "Chrome")

def cerrar_edge():
    """Cierra Microsoft Edge."""
    return cerrar_proceso("msedge.exe", "Edge")

def cerrar_navegador():
    """Cierra las instancias de navegadores comunes."""
    cerrar_proceso("firefox.exe", "Firefox")
    cerrar_proceso("chrome.exe", "Chrome")
    cerrar_proceso("msedge.exe", "Edge")
    return "Navegador cerrado."

def cerrar_administrador_tareas():
    """Cierra el administrador de tareas."""
    return cerrar_proceso("Taskmgr.exe", "Administrador de tareas")

def cerrar_ventana():
    """Cierra la ventana activa actual simulando Alt + F4."""
    user32.keybd_event(0x12, 0, 0, 0) # VK_MENU (Alt)
    user32.keybd_event(0x73, 0, 0, 0) # VK_F4
    time.sleep(0.05)
    user32.keybd_event(0x73, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(0x12, 0, KEYEVENTF_KEYUP, 0)
    return "Ventana cerrada."

def cerrar_pestana():
    """Cierra la pestaña actual simulando Ctrl + W."""
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(0x57, 0, 0, 0) # Tecla 'W'
    time.sleep(0.05)
    user32.keybd_event(0x57, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
    return "Pestaña cerrada."

def minimizar_todo():
    """Minimiza todas las ventanas para ver el escritorio (Win + D)."""
    user32.keybd_event(VK_LWIN, 0, 0, 0)
    user32.keybd_event(0x44, 0, 0, 0) # Tecla 'D'
    time.sleep(0.05)
    user32.keybd_event(0x44, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_LWIN, 0, KEYEVENTF_KEYUP, 0)
    return "Escritorio mostrado."

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004

def clic_en_posicion_raton():
    """Hace un clic izquierdo donde esté situado el puntero del mouse para asegurar el foco."""
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.02)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    time.sleep(0.05)

def escribir_texto_en_cursor(texto, hacer_clic_primero=False, hwnd_destino=None):
    """
    Inserta el texto donde esté enfocado el cursor de texto usando el portapapeles
    de Windows y simulando Ctrl + V. Esto garantiza inserción instantánea,
    respetando tildes, saltos de línea, mayúsculas y caracteres especiales.
    Si se proporciona hwnd_destino, asegura que dicha ventana recupere el foco antes de pegar.
    """
    if not texto:
        return ""

    if hwnd_destino and user32.IsWindow(hwnd_destino):
        cur_fg = user32.GetForegroundWindow()
        if cur_fg != hwnd_destino:
            forzar_primer_plano(hwnd_destino)
            time.sleep(0.06)

    if hacer_clic_primero:
        clic_en_posicion_raton()

    contenido_anterior = None
    try:
        win32clipboard.OpenClipboard()
        if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
            contenido_anterior = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
        win32clipboard.CloseClipboard()
    except Exception:
        try:
            win32clipboard.CloseClipboard()
        except Exception:
            pass

    try:
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, texto)
        win32clipboard.CloseClipboard()
    except Exception as e:
        return f"Error en portapapeles: {e}"

    VK_V = 0x56
    time.sleep(0.03)
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(VK_V, 0, 0, 0)
    time.sleep(0.02)
    user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.03)

    def restaurar():
        time.sleep(0.7)
        if contenido_anterior is not None:
            try:
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, contenido_anterior)
                win32clipboard.CloseClipboard()
            except Exception:
                try:
                    win32clipboard.CloseClipboard()
                except Exception:
                    pass

    threading.Thread(target=restaurar, daemon=True).start()
    return "Texto insertado."
