"""
Módulo HUD Flotante Premium: Píldora visual elegante estilo Antigravity / Windows 11 Fluent.
- Estilo Ecualizador: Barras alineadas en la base inferior con cuerpo blanco brillante
  y remate superior (cap) en gris oscuro/translúcido, basado en el diseño de referencia.
- Color de texto y cuerpo de barras: Gris muy claro / blanco puro (#ffffff / #f4f4f5).
- Ecualizador de audio profesional con 11 barras reactivas al habla y animación viva.
- Círculo de grabación 'REC' con efecto de respiración suave en rojo.
- Arrastrable con el mouse con persistencia de posición en config.json.
- Protección total de foco (WS_EX_NOACTIVATE) y esquinas redondeadas DWM Win11.
"""

import ctypes
import json
import math
import os
import random
import threading
import time
import tkinter as tk
import tkinter.font as tkfont

user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi


class FloatingHUD:
    def __init__(self):
        self.root = None
        self.active = False
        self.modo = "dictado"
        self.volumen = 0.0

        # Configuración del ecualizador inspirado en la referencia
        self.num_bars = 11
        self.bar_w = 4
        self.gap = 3
        self.start_x = 36
        self.y_base = 33
        self.cap_h = 3.5
        self.bar_heights = [4.0] * self.num_bars

        # Ponderación espectral por frecuencias (graves, medios, presencia, agudos)
        self.freq_weights = [0.75, 1.10, 1.35, 1.25, 1.05, 1.30, 1.20, 0.95, 0.85, 1.10, 0.80]

        self._is_dragging = False
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._win_x = 0
        self._win_y = 0
        self._pending_hide = False

        # Paleta de colores fiel a la imagen de referencia (Estilo 3)
        self.color_cuerpo = "#ffffff"       # Cuerpo de las barras blanco brillante
        self.color_cap = "#52525b"          # Remate/punta superior gris oscuro translúcido
        self.color_texto = "#f4f4f5"        # Texto casi blanco muy limpio
        self.color_atenuado = "#9ca3af"     # Gris medio para estado transcribiendo
        self.color_inactivo = "#3f3f46"     # Gris oscuro para reposo

        self.bar_cap_ids = []
        self.bar_body_ids = []

        self._ready = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        self._ready.wait(timeout=3)

    def _cargar_posicion_guardada(self, w, h):
        """Carga la posición guardada en config.json o calcula el centro inferior."""
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        default_x = (sw - w) // 2
        default_y = sh - h - 85

        try:
            cfg_path = os.path.join(os.path.dirname(__file__), "config.json")
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                x = data.get("hud_pos_x")
                y = data.get("hud_pos_y")
                if x is not None and y is not None:
                    x = max(10, min(sw - w - 10, int(x)))
                    y = max(10, min(sh - h - 10, int(y)))
                    return x, y
        except Exception:
            pass

        return default_x, default_y

    def _guardar_posicion(self, x, y):
        """Guarda permanentemente las coordenadas en config.json."""
        try:
            cfg_path = os.path.join(os.path.dirname(__file__), "config.json")
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["hud_pos_x"] = int(x)
                data["hud_pos_y"] = int(y)
                with open(cfg_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _run(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.96)
        self.root.configure(bg="#0c0c0e")

        # Proporción perfecta: 228px de ancho por 44px de alto (márgenes simétricos de 14px)
        w, h = 228, 44
        self._win_x, self._win_y = self._cargar_posicion_guardada(w, h)
        self.root.geometry(f"{w}x{h}+{self._win_x}+{self._win_y}")

        self.root.update_idletasks()
        try:
            h_top = user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()

            # 1. Esquinas redondeadas nativas de Windows 11 (DWM)
            val = ctypes.c_int(2)  # DWMWCP_ROUND
            dwmapi.DwmSetWindowAttribute(h_top, 33, ctypes.byref(val), ctypes.sizeof(val))

            # 2. Estilos Win32 para no robar el foco de escritura del cursor
            GWL_EXSTYLE = -20
            WS_EX_NOACTIVATE = 0x08000000
            WS_EX_TOPMOST = 0x00000008
            WS_EX_TOOLWINDOW = 0x00000080
            ex_style = user32.GetWindowLongW(h_top, GWL_EXSTYLE)
            user32.SetWindowLongW(
                h_top,
                GWL_EXSTYLE,
                ex_style | WS_EX_NOACTIVATE | WS_EX_TOPMOST | WS_EX_TOOLWINDOW
            )
        except Exception:
            pass

        # Canvas principal con borde sutil Fluent
        self.canvas = tk.Canvas(
            self.root,
            width=w,
            height=h,
            bg="#0c0c0e",
            highlightthickness=1,
            highlightbackground="#27272a",
            cursor="fleur"
        )
        self.canvas.pack(fill="both", expand=True)

        # 1. Indicador de grabación circular pulsante REC
        self.rec_glow = self.canvas.create_oval(14, 14, 30, 30, fill="#450a0a", outline="")
        self.rec_dot = self.canvas.create_oval(17, 17, 27, 27, fill="#ef4444", outline="")

        # 2. Barras del ecualizador estilo referencia:
        # Alineadas en la base inferior con cuerpo blanco y remate superior (cap) gris oscuro
        self.bar_cap_ids.clear()
        self.bar_body_ids.clear()

        for i in range(self.num_bars):
            bx = self.start_x + i * (self.bar_w + self.gap)
            # Segmento superior (cap gris oscuro)
            cid = self.canvas.create_rectangle(
                bx, self.y_base - 4, bx + self.bar_w, self.y_base - 2,
                fill=self.color_cap,
                width=0
            )
            # Segmento inferior (cuerpo blanco brillante)
            bid = self.canvas.create_rectangle(
                bx, self.y_base - 2, bx + self.bar_w, self.y_base,
                fill=self.color_cuerpo,
                width=0
            )
            self.bar_cap_ids.append(cid)
            self.bar_body_ids.append(bid)

        # 3. Tipografía limpia alineada exactamente a la línea base inferior del ecualizador
        # Se calcula el descent de la fuente para compensar el padding interno de Tkinter,
        # logrando que las letras descansen milimétricamente sobre la misma línea base inferior que las barras.
        self.font_hud = tkfont.Font(family="Segoe UI", size=9, weight="bold")
        descent = self.font_hud.metrics("descent")
        text_y = self.y_base + descent
        last_bar_right = self.start_x + (self.num_bars - 1) * (self.bar_w + self.gap) + self.bar_w
        text_x = last_bar_right + 12
        self.text_id = self.canvas.create_text(
            text_x, text_y,
            text="Dictando...",
            font=self.font_hud,
            fill=self.color_texto,
            anchor="sw"
        )

        # 4. Bindings de arrastre con el ratón
        self.canvas.bind("<ButtonPress-1>", self._on_drag_start)
        self.canvas.bind("<B1-Motion>", self._on_drag_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_drag_stop)

        self.root.withdraw()
        self._ready.set()
        self._animar()
        self.root.mainloop()

    def _on_drag_start(self, event):
        self._is_dragging = True
        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root
        self._win_x = self.root.winfo_x()
        self._win_y = self.root.winfo_y()

    def _on_drag_motion(self, event):
        dx = event.x_root - self._drag_start_x
        dy = event.y_root - self._drag_start_y
        nx = self._win_x + dx
        ny = self._win_y + dy
        self.root.geometry(f"+{nx}+{ny}")

    def _on_drag_stop(self, event):
        self._is_dragging = False
        self._win_x = self.root.winfo_x()
        self._win_y = self.root.winfo_y()
        self._guardar_posicion(self._win_x, self._win_y)
        if self._pending_hide and not self.active:
            self._pending_hide = False
            self.root.withdraw()

    def _animar(self):
        if self.active and self.root:
            now = time.time()

            # 1. Efecto de respiración suave en el círculo de grabación REC
            fase = (math.sin(now * 5.5) + 1.0) / 2.0
            r_glow = int(60 + 80 * fase)
            glow_hex = f"#{r_glow:02x}080a"
            self.canvas.itemconfig(self.rec_glow, fill=glow_hex)

            r_core = int(220 + 35 * fase)
            core_hex = f"#{r_core:02x}2025"
            self.canvas.itemconfig(self.rec_dot, fill=core_hex)

            # 2. Ecualizador reactivo estilo Referencia 3 (alineado en base)
            raw_rms = max(0.0, self.volumen)
            vol_factor = min(1.0, math.sqrt(raw_rms) * 3.8)

            for i in range(self.num_bars):
                # Ondulación viva armónica continua (mantiene movimiento fluido)
                wave = math.sin(now * 8.0 + i * 0.8) * 0.30 + 0.35
                # Dinamismo espectral (fluctuación de frecuencias de audio)
                noise = random.uniform(0.70, 1.30)

                alt_base = 3.5 + 3.0 * wave
                alt_voz = 16.5 * vol_factor * self.freq_weights[i] * noise
                target_h = max(4.0, min(22.0, alt_base + alt_voz))

                # Inercia natural: subida inmediata (0.70) para reflejar la voz y caída suave (0.35)
                if target_h > self.bar_heights[i]:
                    self.bar_heights[i] += (target_h - self.bar_heights[i]) * 0.70
                else:
                    self.bar_heights[i] += (target_h - self.bar_heights[i]) * 0.35

                h_val = self.bar_heights[i]
                bx = self.start_x + i * (self.bar_w + self.gap)

                y_top = self.y_base - h_val
                y_cap_bottom = min(self.y_base - 2, y_top + self.cap_h)

                # Segmento de remate superior (cap)
                self.canvas.coords(self.bar_cap_ids[i], bx, y_top, bx + self.bar_w, y_cap_bottom)
                self.canvas.itemconfig(self.bar_cap_ids[i], fill=self.color_cap)

                # Segmento de cuerpo blanco (desde el cap hasta la base)
                self.canvas.coords(self.bar_body_ids[i], bx, y_cap_bottom, bx + self.bar_w, self.y_base)
                self.canvas.itemconfig(self.bar_body_ids[i], fill=self.color_cuerpo)

        self.root.after(30, self._animar)

    def iniciar_grabacion(self, modo="dictado"):
        """Muestra el HUD y activa la animación del ecualizador."""
        self.modo = modo
        self.active = True
        self.volumen = 0.02
        self._pending_hide = False
        if self.root:
            def _upd():
                texto = "Dictando..." if modo == "dictado" else "Escuchando..."
                self.canvas.itemconfig(self.text_id, text=texto, fill=self.color_texto)
                for cid in self.bar_cap_ids:
                    self.canvas.itemconfig(cid, fill=self.color_cap)
                for bid in self.bar_body_ids:
                    self.canvas.itemconfig(bid, fill=self.color_cuerpo)
                self.root.deiconify()
            self.root.after(0, _upd)

    def actualizar_volumen(self, rms):
        """Alimenta el nivel RMS del micrófono para animar las barras en tiempo real."""
        self.volumen = rms

    def indicar_procesando(self):
        """Muestra estado de procesamiento y apaga temporalmente el ecualizador."""
        if self.root:
            def _upd():
                self.canvas.itemconfig(self.text_id, text="Transcribiendo...", fill=self.color_atenuado)
                self.canvas.itemconfig(self.rec_glow, fill="#18181b")
                self.canvas.itemconfig(self.rec_dot, fill="#71717a")
                for i in range(self.num_bars):
                    bx = self.start_x + i * (self.bar_w + self.gap)
                    self.canvas.coords(self.bar_cap_ids[i], bx, self.y_base - 3, bx + self.bar_w, self.y_base - 1.5)
                    self.canvas.itemconfig(self.bar_cap_ids[i], fill="#27272a")
                    self.canvas.coords(self.bar_body_ids[i], bx, self.y_base - 1.5, bx + self.bar_w, self.y_base)
                    self.canvas.itemconfig(self.bar_body_ids[i], fill=self.color_inactivo)
            self.root.after(0, _upd)

    def ocultar(self):
        """Oculta la ventana (o espera si el usuario está arrastrándola con el mouse)."""
        self.active = False
        if self.root:
            def _upd():
                if self._is_dragging:
                    self._pending_hide = True
                else:
                    self.root.withdraw()
            self.root.after(0, _upd)
