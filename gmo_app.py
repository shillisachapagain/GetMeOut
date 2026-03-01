import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import threading
import queue
import time
import os
import json
import math
import random

# pyaudio, vosk, and pygame imports

try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False

try:
    from vosk import Model, KaldiRecognizer
    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False

try:
    import pygame
    pygame.mixer.init()
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False

#config

VOSK_MODEL_PATH = "./vosk-model-small-en-us-0.15"
DECOY_AUDIO_PATH = "./decoy_call.wav"
SAMPLE_RATE = 16000
CHUNK_SIZE = 4096

DEFAULT_KEYWORDS = ["help", "emergency"]
DEFAULT_DELAY = 3.0

CALLER_PROFILES = [
    {"name": "Mom",               "number": "+1 (555) 842-1923"},
    {"name": "Shillisa",         "number": "+1 (555) 203-4411"},
    {"name": "Basma",              "number": "+1 (555) 671-8802"},
    {"name": "Karelle", "number": "+1 (555) 900-0012"},
    {"name": "Nilaya",             "number": "+1 (555) 358-2247"},
]

# colour palette

C = {
    "bg":        "#0a0e1a",
    "card":      "#111827",
    "surface":   "#1a2235",
    "accent":    "#00d4aa",
    "accent_d":  "#00856a",
    "danger":    "#ff4757",
    "warn":      "#ffa502",
    "text":      "#e8ecf4",
    "text_s":    "#7a8ba8",
    "text_m":    "#3d4f6a",
    "green":     "#2ed573",
    "red":       "#ff4757",
    "border":    "#1e2d45",
}


# audio listener thread

class AudioListener:
    def __init__(self, keywords, signal_queue, status_cb):
        self.keywords = [k.lower().strip() for k in keywords]
        self.signal_queue = signal_queue
        self.status_cb = status_cb
        self._stop = threading.Event()
        self._triggered = False

    def stop(self):
        self._stop.set()

    def run(self):
        if not (PYAUDIO_AVAILABLE and VOSK_AVAILABLE and os.path.exists(VOSK_MODEL_PATH)):
            mode = "DEMO" if not (PYAUDIO_AVAILABLE and VOSK_AVAILABLE) else "NO MODEL"
            self.status_cb(f"🎙 {mode} mode — trigger fires in 12 seconds for testing", "warn")
            self._simulate()
            return

        try:
            model = Model(VOSK_MODEL_PATH)
            rec = KaldiRecognizer(model, SAMPLE_RATE)
            pa = pyaudio.PyAudio()
            stream = pa.open(format=pyaudio.paInt16, channels=1,
                             rate=SAMPLE_RATE, input=True,
                             frames_per_buffer=CHUNK_SIZE)

            self.status_cb("🎙 Listening for keywords…", "active")

            while not self._stop.is_set():
                data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                if rec.AcceptWaveform(data):
                    text = json.loads(rec.Result()).get("text", "").lower()
                else:
                    text = json.loads(rec.PartialResult()).get("partial", "").lower()
                if text and not self._triggered:
                    self._check(text)

            stream.stop_stream()
            stream.close()
            pa.terminate()

        except Exception as e:
            self.status_cb(f"Audio error: {e}", "error")

    def _simulate(self):
        for _ in range(120):
            if self._stop.is_set():
                return
            time.sleep(0.1)
        if not self._triggered:
            self._triggered = True
            self.signal_queue.put("TRIGGER")

    def _check(self, text):
        for kw in self.keywords:
            if kw in text:
                self._triggered = True
                self.signal_queue.put("TRIGGER")
                return


# fake call window

class FakeCallWindow(ctk.CTkToplevel):
    def __init__(self, caller, on_dismiss):
        super().__init__()
        self.caller = caller
        self.on_dismiss = on_dismiss
        self._active = False
        self._ring_id = None
        self._elapsed = 0

        self.title("")
        self.resizable(False, False)
        self.configure(fg_color=C["bg"])
        self.attributes("-topmost", True)
        self.attributes("-fullscreen", True)
        self.protocol("WM_DELETE_WINDOW", lambda: None)

        self._build()
        self._animate(0)

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        root = ctk.CTkFrame(self, fg_color=C["bg"])
        root.grid(sticky="nsew")
        root.grid_columnconfigure(0, weight=1)

        # status bar
        sb = ctk.CTkFrame(root, fg_color=C["card"], height=40, corner_radius=0)
        sb.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(sb, text="●●●●  WiFi  🔋",
                     font=ctk.CTkFont("Courier New", 11),
                     text_color=C["text_s"]).pack(side="right", padx=16, pady=10)

        # avatar canvas
        self.canvas = tk.Canvas(root, width=180, height=180,
                                bg=C["bg"], highlightthickness=0)
        self.canvas.grid(row=1, column=0, pady=(70, 16))

        self.ring_outer = self.canvas.create_oval(5, 5, 175, 175, outline=C["accent"], width=1)
        self.ring_mid   = self.canvas.create_oval(20, 20, 160, 160, outline=C["accent"], width=1)
        self.canvas.create_oval(35, 35, 145, 145, fill=C["surface"], outline="")
        initials = "".join(w[0].upper() for w in self.caller["name"].split()[:2] if w.isalpha())
        self.canvas.create_text(90, 90, text=initials or "?",
                                font=("Georgia", 30, "bold"), fill=C["accent"])

        # name / number
        ctk.CTkLabel(root, text=self.caller["name"],
                     font=ctk.CTkFont("Georgia", 34, "bold"),
                     text_color=C["text"]).grid(row=2, column=0)

        ctk.CTkLabel(root, text=self.caller["number"],
                     font=ctk.CTkFont("Courier New", 15),
                     text_color=C["text_s"]).grid(row=3, column=0, pady=(4, 2))

        self.sub_label = ctk.CTkLabel(root, text="Incoming Call…",
                                       font=ctk.CTkFont("Helvetica", 13),
                                       text_color=C["accent"])
        self.sub_label.grid(row=4, column=0, pady=(0, 50))

        self.timer_lbl = ctk.CTkLabel(root, text="",
                                       font=ctk.CTkFont("Courier New", 26, "bold"),
                                       text_color=C["text"])
        self.timer_lbl.grid(row=5, column=0, pady=(0, 10))

        # buttons
        btn_row = ctk.CTkFrame(root, fg_color="transparent")
        btn_row.grid(row=6, column=0, pady=(0, 70))

        # decline
        df = ctk.CTkFrame(btn_row, fg_color="transparent")
        df.pack(side="left", padx=45)
        self.dec_btn = ctk.CTkButton(df, text="✕", width=72, height=72,
                                      corner_radius=36, fg_color=C["red"],
                                      hover_color="#cc2233",
                                      font=ctk.CTkFont("Helvetica", 26, "bold"),
                                      command=self._decline)
        self.dec_btn.pack()
        ctk.CTkLabel(df, text="Decline", font=ctk.CTkFont("Helvetica", 12),
                     text_color=C["text_s"]).pack(pady=(6, 0))

        # accept
        af = ctk.CTkFrame(btn_row, fg_color="transparent")
        af.pack(side="right", padx=45)
        self.acc_btn = ctk.CTkButton(af, text="✆", width=72, height=72,
                                      corner_radius=36, fg_color=C["green"],
                                      hover_color="#25c060",
                                      font=ctk.CTkFont("Helvetica", 26, "bold"),
                                      command=self._accept)
        self.acc_btn.pack()
        ctk.CTkLabel(af, text="Accept", font=ctk.CTkFont("Helvetica", 12),
                     text_color=C["text_s"]).pack(pady=(6, 0))

        # end call button (hidden until accepted)
        self.end_btn = ctk.CTkButton(root, text="End Call", width=180, height=50,
                                      corner_radius=25, fg_color=C["red"],
                                      hover_color="#cc2233",
                                      font=ctk.CTkFont("Helvetica", 15, "bold"),
                                      command=self._end)
        # intentionally not gridded yet

    def _animate(self, step):
        if not self.winfo_exists() or self._active:
            return
        t = abs(math.sin(step * 0.12))
        self.canvas.itemconfig(self.ring_outer, outline=self._lerp(C["bg"], C["accent"], t * 0.45))
        t2 = abs(math.sin(step * 0.12 + 1.2))
        self.canvas.itemconfig(self.ring_mid, outline=self._lerp(C["bg"], C["accent"], t2 * 0.3))
        self._ring_id = self.after(50, lambda: self._animate(step + 1))

    def _lerp(self, h1, h2, t):
        r = lambda h: (int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16))
        c1, c2 = r(h1), r(h2)
        return "#{:02x}{:02x}{:02x}".format(
            int(c1[0] + (c2[0]-c1[0])*t),
            int(c1[1] + (c2[1]-c1[1])*t),
            int(c1[2] + (c2[2]-c1[2])*t))

    def _accept(self):
        self._active = True
        if self._ring_id:
            self.after_cancel(self._ring_id)
        self.acc_btn.grid_remove()
        self.dec_btn.configure(state="disabled")
        self.sub_label.configure(text="Connected")
        self.timer_lbl.configure(text="0:00")
        self.end_btn.grid(row=7, column=0, pady=(0, 40))

        if PYGAME_AVAILABLE and os.path.exists(DECOY_AUDIO_PATH):
            pygame.mixer.music.load(DECOY_AUDIO_PATH)
            pygame.mixer.music.play()

        self._tick()

    def _tick(self):
        if not self.winfo_exists() or not self._active:
            return
        self._elapsed += 1
        m, s = divmod(self._elapsed, 60)
        self.timer_lbl.configure(text=f"{m}:{s:02d}")
        self.after(1000, self._tick)

    def _decline(self):
        self._cleanup()

    def _end(self):
        if PYGAME_AVAILABLE:
            pygame.mixer.music.stop()
        self._cleanup()

    def _cleanup(self):
        self._active = False
        self.destroy()
        self.on_dismiss()


# main dashboard

class GMOApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")

        self.title("GMO - Get Me Out")
        self.geometry("520x730")
        self.resizable(False, False)
        self.configure(fg_color=C["bg"])

        self._listener = None
        self._listener_thread = None
        self._queue = queue.Queue()
        self._active = False
        self._call_window = None
        self._keywords = DEFAULT_KEYWORDS.copy()
        self._delay = DEFAULT_DELAY
        self._caller = CALLER_PROFILES[0]

        self._build()
        self._poll()

    # GUI Build

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        # Header
        hdr = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=0, height=68)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_propagate(False)
        hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hdr, text="⬡  Get Me Out",
                     font=ctk.CTkFont("Courier New", 22, "bold"),
                     text_color=C["accent"]).grid(row=0, column=0, padx=22, pady=16, sticky="w")
        self._dot = ctk.CTkLabel(hdr, text="● DORMANT",
                                  font=ctk.CTkFont("Courier New", 11),
                                  text_color=C["text_m"])
        self._dot.grid(row=0, column=1, padx=22)

        # keywords card
        kc = self._card(1)
        ctk.CTkLabel(kc, text="TRIGGER KEYWORDS",
                     font=ctk.CTkFont("Courier New", 10, "bold"),
                     text_color=C["text_m"]).grid(row=0, column=0, padx=16, pady=(14, 4), sticky="w")
        self._kw_label = ctk.CTkLabel(kc, text=self._fmt_kw(),
                                       font=ctk.CTkFont("Georgia", 13),
                                       text_color=C["text"], wraplength=450, justify="left")
        self._kw_label.grid(row=1, column=0, padx=16, pady=(0, 8), sticky="w")

        add_row = ctk.CTkFrame(kc, fg_color="transparent")
        add_row.grid(row=2, column=0, padx=16, pady=(0, 8), sticky="ew")
        add_row.grid_columnconfigure(0, weight=1)
        self._kw_entry = ctk.CTkEntry(add_row, placeholder_text="Add keyword…",
                                       fg_color=C["surface"], border_color=C["border"],
                                       text_color=C["text"],
                                       font=ctk.CTkFont("Courier New", 13))
        self._kw_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._kw_entry.bind("<Return>", lambda e: self._add_kw())
        ctk.CTkButton(add_row, text="Add", width=60, height=32,
                      fg_color=C["accent_d"], hover_color=C["accent"],
                      font=ctk.CTkFont("Courier New", 12),
                      command=self._add_kw).grid(row=0, column=1)
        ctk.CTkButton(kc, text="Reset defaults", height=26, width=120,
                      fg_color="transparent", hover_color=C["surface"],
                      border_width=1, border_color=C["border"],
                      font=ctk.CTkFont("Courier New", 10),
                      text_color=C["text_s"],
                      command=self._reset_kw).grid(row=3, column=0, padx=16, pady=(0, 12), sticky="e")

        # caller card
        cc = self._card(2)
        ctk.CTkLabel(cc, text="FAKE CALLER IDENTITY",
                     font=ctk.CTkFont("Courier New", 10, "bold"),
                     text_color=C["text_m"]).grid(row=0, column=0, padx=16, pady=(14, 8), sticky="w")
        self._caller_var = ctk.StringVar(value=CALLER_PROFILES[0]["name"])
        ctk.CTkOptionMenu(cc,
                          values=[p["name"] for p in CALLER_PROFILES],
                          variable=self._caller_var,
                          fg_color=C["surface"], button_color=C["accent_d"],
                          button_hover_color=C["accent"],
                          dropdown_fg_color=C["surface"],
                          text_color=C["text"],
                          font=ctk.CTkFont("Georgia", 13),
                          command=self._on_caller).grid(row=1, column=0, padx=16, pady=(0, 14), sticky="ew")

        # delay card
        dc = self._card(3)
        dh = ctk.CTkFrame(dc, fg_color="transparent")
        dh.grid(row=0, column=0, padx=16, pady=(14, 4), sticky="ew")
        dh.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(dh, text="TRIGGER DELAY",
                     font=ctk.CTkFont("Courier New", 10, "bold"),
                     text_color=C["text_m"]).grid(row=0, column=0, sticky="w")
        self._delay_lbl = ctk.CTkLabel(dh, text=f"{self._delay:.1f}s",
                                        font=ctk.CTkFont("Courier New", 13, "bold"),
                                        text_color=C["accent"])
        self._delay_lbl.grid(row=0, column=1, sticky="e")
        ctk.CTkSlider(dc, from_=0, to=15, number_of_steps=30,
                      progress_color=C["accent"], button_color=C["accent"],
                      button_hover_color=C["text"],
                      command=self._on_delay).grid(row=1, column=0, padx=16, pady=(0, 14), sticky="ew")

        # transcript card
        tc = self._card(4)
        self.grid_rowconfigure(4, weight=1)
        tc.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(tc, text="LIVE TRANSCRIPT",
                     font=ctk.CTkFont("Courier New", 10, "bold"),
                     text_color=C["text_m"]).grid(row=0, column=0, padx=16, pady=(14, 4), sticky="w")
        self._log = ctk.CTkTextbox(tc, height=100,
                                    fg_color=C["surface"],
                                    text_color=C["text_s"],
                                    font=ctk.CTkFont("Courier New", 12),
                                    border_width=1, border_color=C["border"],
                                    state="disabled")
        self._log.grid(row=1, column=0, padx=16, pady=(0, 14), sticky="nsew")

        # status banner
        self._banner = ctk.CTkLabel(self,
                                     text="System dormant. Press Start GMO to activate.",
                                     font=ctk.CTkFont("Courier New", 11),
                                     text_color=C["text_m"], wraplength=460)
        self._banner.grid(row=5, column=0, padx=20, pady=(4, 8))

        # main button
        self._btn = ctk.CTkButton(self, text="▶  START GMO",
                                   height=56, corner_radius=10,
                                   fg_color=C["accent_d"], hover_color=C["accent"],
                                   font=ctk.CTkFont("Courier New", 16, "bold"),
                                   text_color=C["bg"],
                                   command=self._toggle)
        self._btn.grid(row=6, column=0, padx=20, pady=(0, 24), sticky="ew")

    def _card(self, row):
        f = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=12)
        f.grid(row=row, column=0, padx=20, pady=(12, 0), sticky="ew")
        f.grid_columnconfigure(0, weight=1)
        return f

    # keyword helpers

    def _fmt_kw(self):
        return "  ·  ".join(f'"{k}"' for k in self._keywords)

    def _add_kw(self):
        v = self._kw_entry.get().strip()
        if v and v.lower() not in [k.lower() for k in self._keywords]:
            self._keywords.append(v)
            self._kw_label.configure(text=self._fmt_kw())
            self._kw_entry.delete(0, "end")
            if self._listener:
                self._listener.keywords = [k.lower() for k in self._keywords]

    def _reset_kw(self):
        self._keywords = DEFAULT_KEYWORDS.copy()
        self._kw_label.configure(text=self._fmt_kw())
        if self._listener:
            self._listener.keywords = [k.lower() for k in self._keywords]

    # callbacks

    def _on_caller(self, name):
        self._caller = next(p for p in CALLER_PROFILES if p["name"] == name)

    def _on_delay(self, v):
        self._delay = round(float(v), 1)
        self._delay_lbl.configure(text=f"{self._delay:.1f}s")

    # GMO control

    def _toggle(self):
        if self._active:
            self._stop()
        else:
            self._start()

    def _start(self):
        self._active = True
        self._btn.configure(text="■  STOP GMO",
                             fg_color=C["danger"], hover_color="#cc2233")
        self._dot.configure(text="● ACTIVE", text_color=C["green"])
        self._write_log("— Listening started —")

        self._listener = AudioListener(self._keywords, self._queue, self._listener_status)
        self._listener_thread = threading.Thread(target=self._listener.run, daemon=True)
        self._listener_thread.start()

    def _stop(self):
        self._active = False
        if self._listener:
            self._listener.stop()
            self._listener = None
        self._btn.configure(text="▶  START GMO",
                             fg_color=C["accent_d"], hover_color=C["accent"])
        self._dot.configure(text="● DORMANT", text_color=C["text_m"])
        self._set_banner("System dormant. Press Start GMO to activate.", "m")
        self._write_log("— Listening stopped —")

    # queue polling and call flow

    def _poll(self):
        try:
            while True:
                msg = self._queue.get_nowait()
                if msg == "TRIGGER" and not self._call_window:
                    self._triggered()
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _triggered(self):
        self._set_banner(f"🔑 Keyword detected! Fake call in {self._delay:.0f}s…", "w")
        self._write_log("[KEYWORD DETECTED]")
        self.after(int(self._delay * 1000), self._launch_call)

    def _launch_call(self):
        if not self.winfo_exists():
            return
        self._call_window = FakeCallWindow(self._caller, on_dismiss=self._call_dismissed)
        self._call_window.lift()

    def _call_dismissed(self):
        self._call_window = None
        self._set_banner("Call ended. Listening resumed…", "a")
        if self._listener:
            self._listener._triggered = False

    # helpers

    def _listener_status(self, msg, kind):
        self.after(0, lambda: self._set_banner(msg, kind[0]))
        if kind != "active":
            self.after(0, lambda: self._write_log(msg))

    def _set_banner(self, text, kind="m"):
        colors = {"a": C["accent"], "w": C["warn"], "e": C["danger"], "m": C["text_m"]}
        self._banner.configure(text=text, text_color=colors.get(kind, C["text_m"]))

    def _write_log(self, text):
        self._log.configure(state="normal")
        self._log.insert("end", text + "\n")
        self._log.see("end")
        self._log.configure(state="disabled")


# entry point

if __name__ == "__main__":
    app = GMOApp()
    app.mainloop()