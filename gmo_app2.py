import customtkinter as ctk
from customtkinter import filedialog
from PIL import Image, ImageDraw
import pygame
import os
import json
import time
import queue
import threading
from threading import Thread


# optional heavy imports (graceful fallback for dev/testing)
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


# config
VOSK_MODEL_PATH = "./vosk-model-small-en-us-0.15"
SAMPLE_RATE = 16000
CHUNK_SIZE = 4096

DEFAULT_KEYWORDS = ["help", "emergency"]
DEFAULT_DELAY = 3.0

CALLER_PROFILES = [
    {"name": "Basma",    "number": "+1 (555) 671-8802", "audio": "basma.mp3"},
    {"name": "Mom",      "number": "+1 (555) 842-1923", "audio": "mom.mp3"},
    {"name": "Shillisa", "number": "+1 (555) 203-4411", "audio": "shillisa.mp3"},
    {"name": "Karelle",  "number": "+1 (555) 900-0012", "audio": "karelle2.mp3"},
    {"name": "Nilaya",   "number": "+1 (555) 358-2247", "audio": "nilaya.mp3"},
]

# cute pink & green color scheme
BG_COLOR       = "#e88ca1"
CARD_COLOR     = "#efbac6"
ACCENT_GREEN1  = "#A8E6B8"
ACCENT_GREEN2  = "#6FD98E"
ACCENT_RED     = "#FF6B9D"
SHADOW_COLOR   = "#E085C0"
TEXT_PRIMARY   = "#FFF6E4"
TEXT_SECONDARY = "#7B4A8A"


# Audio Listener Thread

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
            # fall back to demo mode if dependencies or model are missing
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
        # wait 12 seconds then fire trigger for demo/testing
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


# Main App

class GMOApp:
    def __init__(self):
        # initialize pygame mixer for audio playback
        pygame.mixer.init()

        # state variables
        self.state = {
            "selected_mp3_path": CALLER_PROFILES[0]["audio"],
            "ringtone_path":     "assets/ringtone.mp3",
            "caller_image_path": "assets/caller.png",
            "gmo_active":        False,
            "ringtone_playing":  False,
        }

        # keyword & listener state
        self._keywords        = DEFAULT_KEYWORDS.copy()
        self._delay           = DEFAULT_DELAY
        self._caller          = CALLER_PROFILES[0]
        self._listener        = None
        self._listener_thread = None
        self._queue           = queue.Queue() 
        self._ringtone_thread = None

        # store references for ui updates
        self.caller_image_cache = None
        self.logo_image         = None
        self._status_label      = None
        self._call_status       = None
        self._call_elapsed      = 0
        self._mic_dot   = None
        self._mic_label = None

        # create the main window
        self.app = ctk.CTk()
        self.app.title("GMO - Get Me Out")
        self.app.geometry("600x900")
        self.app.attributes('-topmost', False)
        self.app.configure(fg_color=BG_COLOR)

        self.show_dashboard()
        self._poll()
        self.app.mainloop()

    # queue polling 

    def _poll(self):
        # check the listener queue every 100ms for keyword triggers
        try:
            while True:
                msg = self._queue.get_nowait()
                if msg == "TRIGGER" and self.state["gmo_active"]:
                    self._on_keyword_detected()
        except queue.Empty:
            pass
        self.app.after(100, self._poll)

    def _on_keyword_detected(self):
        self._update_status(f"🔑 Keyword detected! Call in {self._delay:.0f}s…")
        self.app.after(int(self._delay * 1000), self.show_incoming_call)

    def _update_status(self, text):
        if self._status_label and self._status_label.winfo_exists():
            self._status_label.configure(text=text)

    # listener control 

    def _start_listener(self):
        self.state["gmo_active"] = True
        self._listener = AudioListener(self._keywords, self._queue, self._listener_status_cb)
        self._listener_thread = threading.Thread(target=self._listener.run, daemon=True)
        self._listener_thread.start()

    def _stop_listener(self):
        self.state["gmo_active"] = False
        if self._listener:
            self._listener.stop()
            self._listener = None

    def _listener_status_cb(self, msg, kind):
        # called from listener thread, must schedule on main thread
        self.app.after(0, lambda: self._update_status(msg))

    #  ringtone 

    def _play_ringtone_loop(self):
        try:
            if os.path.exists(self.state["ringtone_path"]):
                pygame.mixer.music.load(self.state["ringtone_path"])
                pygame.mixer.music.play(-1)
                while self.state["ringtone_playing"]:
                    pygame.time.delay(100)
                pygame.mixer.music.stop()
        except Exception as e:
            print(f"Ringtone error: {e}")

    def _start_ringtone(self):
        if self._ringtone_thread and self._ringtone_thread.is_alive():
            self.state["ringtone_playing"] = False
            self._ringtone_thread.join(timeout=1)
        self.state["ringtone_playing"] = True
        self._ringtone_thread = Thread(target=self._play_ringtone_loop, daemon=True)
        self._ringtone_thread.start()

    def _stop_ringtone(self):
        self.state["ringtone_playing"] = False
        pygame.mixer.music.stop()
        pygame.time.delay(100)

    #  image helpers 

    def _load_logo(self, path="assets/logo.png", w=60, h=60):
        try:
            if os.path.exists(path):
                img = Image.open(path).convert("RGBA")
                img = img.resize((w, h), Image.Resampling.LANCZOS)
                self.logo_image = ctk.CTkImage(light_image=img, size=(w, h))
                return self.logo_image
        except Exception as e:
            print(f"Error loading logo: {e}")
        return None

    def _load_caller_image(self, path="assets/caller.png", w=60, h=60):
        try:
            if not os.path.exists(path):
                return None
            # load and convert image
            img = Image.open(path)
            if img.mode == 'RGBA':
                # create a white background and paste with alpha
                bg = Image.new('RGB', img.size, (255, 255, 255))
                bg.paste(img, mask=img.split()[3])
                img = bg
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            # resize and center on canvas
            img.thumbnail((w, h), Image.Resampling.LANCZOS)
            final = Image.new('RGB', (w, h), (255, 255, 255))
            final.paste(img, ((w - img.width) // 2, (h - img.height) // 2))
            # cache to prevent garbage collection
            ctk_img = ctk.CTkImage(light_image=final, size=(w, h))
            self.caller_image_cache = ctk_img
            return ctk_img
        except Exception as e:
            print(f"Error loading caller image: {e}")
            return None

    def _make_avatar(self, name, size=60):
        # generate an initials avatar when no caller image is available
        initials = "".join(p[0].upper() for p in name.split()[:2] if p.isalpha())
        img = Image.new('RGB', (size, size), color=ACCENT_GREEN2)
        draw = ImageDraw.Draw(img)
        try:
            from PIL import ImageFont
            font = ImageFont.load_default()
            bb = draw.textbbox((0, 0), initials, font=font)
            draw.text(((size-(bb[2]-bb[0]))//2, (size-(bb[3]-bb[1]))//2),
                      initials, fill='#ffffff', font=font)
        except Exception:
            pass
        ctk_img = ctk.CTkImage(light_image=img, size=(size, size))
        self.caller_image_cache = ctk_img
        return ctk_img

    #  keyword helpers 

    def _fmt_kw(self):
        return "  ·  ".join(f'"{k}"' for k in self._keywords)

    def _add_kw(self):
        v = self._kw_entry.get().strip()
        if v and v.lower() not in [k.lower() for k in self._keywords]:
            self._keywords.append(v)
            self._kw_display.configure(text=self._fmt_kw())
            self._kw_entry.delete(0, "end")
            if self._listener:
                self._listener.keywords = [k.lower() for k in self._keywords]

    def _reset_kw(self):
        self._keywords = DEFAULT_KEYWORDS.copy()
        self._kw_display.configure(text=self._fmt_kw())
        if self._listener:
            self._listener.keywords = [k.lower() for k in self._keywords]

    def _on_caller(self, name):
        self._caller = next(p for p in CALLER_PROFILES if p["name"] == name)

    def _on_delay(self, v):
        self._delay = round(float(v), 1)
        self._delay_lbl.configure(text=f"{self._delay:.1f}s")

    def _pick_audio(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("Audio Files", "*.mp3 *.wav"), ("All Files", "*.*")],
            title="Select Decoy Audio File"
        )
        if file_path:
            self.state["selected_mp3_path"] = file_path
            self._audio_display.configure(text=f"📁 {os.path.basename(file_path)}")

    #  pink card helper 

    def _pink_card(self, parent, title, body):
        shadow = ctk.CTkFrame(parent, fg_color=SHADOW_COLOR, corner_radius=18)
        shadow.pack(fill="x", pady=(0, 16), padx=3)
        card = ctk.CTkFrame(shadow, fg_color=CARD_COLOR, corner_radius=16)
        card.pack(fill="x", padx=3, pady=3)
        ctk.CTkLabel(card, text=title,
            font=("Greater Theory", 13, "bold"),
            text_color=TEXT_PRIMARY).pack(anchor="w", padx=20, pady=(16, 6))
        ctk.CTkLabel(card, text=body,
            font=("Poppins", 13),
            text_color=TEXT_SECONDARY,
            justify="left").pack(anchor="nw", padx=20, pady=(0, 16))


#  Dashboard Screen

    def show_dashboard(self):
        self._stop_listener()
        self._stop_ringtone()

        for w in self.app.winfo_children():
            w.destroy()

        self.app.geometry("600x900")
        self.app.attributes('-topmost', False)

        scroll = ctk.CTkScrollableFrame(self.app, fg_color=BG_COLOR)
        scroll.pack(fill="both", expand=True)
        main = ctk.CTkFrame(scroll, fg_color=BG_COLOR)
        main.pack(fill="both", expand=True, padx=20, pady=20)

        # Top Status Bar
        shadow_bar = ctk.CTkFrame(main, fg_color=SHADOW_COLOR, corner_radius=16)
        shadow_bar.pack(fill="x", pady=(0, 20), padx=3)
        status_bar = ctk.CTkFrame(shadow_bar, fg_color=CARD_COLOR, corner_radius=14)
        status_bar.pack(fill="x", padx=3, pady=3)
        mic_frame = ctk.CTkFrame(status_bar, fg_color=CARD_COLOR)
        mic_frame.pack(side="left", padx=20, pady=14)
        ctk.CTkLabel(mic_frame, text="●", font=("Arial", 20),
            text_color=ACCENT_RED).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(mic_frame, text="Mic: OFF",
            font=("Poppins", 13, "bold"),
            text_color=TEXT_SECONDARY).pack(side="left")

        # Header
        hdr = ctk.CTkFrame(main, fg_color=BG_COLOR)
        hdr.pack(fill="x", pady=(0, 25))
        logo = self._load_logo()
        if logo:
            ctk.CTkLabel(hdr, image=logo, text="").pack(side="left", padx=(0, 12))
        title_box = ctk.CTkFrame(hdr, fg_color=BG_COLOR)
        title_box.pack(side="left")
        ctk.CTkLabel(title_box, text="GMO",
            font=("Greater Theory", 48, "bold"),
            text_color=TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(title_box, text="Get Me Out — Audio Security",
            font=("Poppins", 15, "bold"),
            text_color=TEXT_SECONDARY).pack(anchor="w")

        # Instruction Card
        self._pink_card(main, "📋 How It Works",
            "1. Add your trigger keywords below\n"
            "2. Choose your fake caller & decoy audio\n"
            "3. Press 'Get Me Out' — the app listens and\n"
            "triggers a fake call when it hears a keyword")

        # Keywords
        kw_shadow = ctk.CTkFrame(main, fg_color=SHADOW_COLOR, corner_radius=18)
        kw_shadow.pack(fill="x", pady=(0, 16), padx=3)
        kw_card = ctk.CTkFrame(kw_shadow, fg_color=CARD_COLOR, corner_radius=16)
        kw_card.pack(fill="x", padx=3, pady=3)
        ctk.CTkLabel(kw_card, text="🔑 Trigger Keywords",
            font=("Greater Theory", 13, "bold"),
            text_color=TEXT_PRIMARY).pack(anchor="w", padx=20, pady=(16, 6))
        self._kw_display = ctk.CTkLabel(kw_card, text=self._fmt_kw(),
            font=("Poppins", 12),
            text_color=TEXT_SECONDARY,
            wraplength=500, justify="left")
        self._kw_display.pack(anchor="w", padx=20, pady=(0, 8))
        kw_row = ctk.CTkFrame(kw_card, fg_color=CARD_COLOR)
        kw_row.pack(fill="x", padx=20, pady=(0, 8))
        self._kw_entry = ctk.CTkEntry(kw_row, placeholder_text="Add keyword…",
            fg_color=BG_COLOR,
            border_color=SHADOW_COLOR,
            text_color=TEXT_SECONDARY,
            font=("Poppins", 13))
        self._kw_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._kw_entry.bind("<Return>", lambda e: self._add_kw())
        ctk.CTkButton(kw_row, text="Add", width=70, height=34, corner_radius=10,
            fg_color=ACCENT_GREEN2, hover_color=ACCENT_GREEN1,
            text_color=TEXT_PRIMARY, font=("Greater Theory", 10, "bold"),
            command=self._add_kw).pack(side="left")
        ctk.CTkButton(kw_card, text="Reset defaults", height=26, width=130,
            fg_color="transparent", border_width=1,
            border_color=ACCENT_RED, text_color=TEXT_SECONDARY,
            font=("Poppins", 10),
            command=self._reset_kw).pack(anchor="e", padx=20, pady=(0, 12))

        # Caller Selection
        caller_shadow = ctk.CTkFrame(main, fg_color=SHADOW_COLOR, corner_radius=18)
        caller_shadow.pack(fill="x", pady=(0, 16), padx=3)
        caller_card = ctk.CTkFrame(caller_shadow, fg_color=CARD_COLOR, corner_radius=16)
        caller_card.pack(fill="x", padx=3, pady=3)
        ctk.CTkLabel(caller_card, text="👤 Caller",
            font=("Greater Theory", 13, "bold"),
            text_color=TEXT_PRIMARY).pack(anchor="w", padx=20, pady=(16, 8))
        self._caller_var = ctk.StringVar(value=CALLER_PROFILES[0]["name"])
        ctk.CTkOptionMenu(caller_card,
            values=[p["name"] for p in CALLER_PROFILES],
            variable=self._caller_var,
            fg_color=BG_COLOR,
            button_color=ACCENT_GREEN2,
            button_hover_color=ACCENT_GREEN1,
            dropdown_fg_color=CARD_COLOR,
            text_color=TEXT_SECONDARY,
            font=("Poppins", 13),
            command=self._on_caller).pack(fill="x", padx=20, pady=(0, 16))

        # DELAY SLIDER
        delay_shadow = ctk.CTkFrame(main, fg_color=SHADOW_COLOR, corner_radius=18)
        delay_shadow.pack(fill="x", pady=(0, 16), padx=3)
        delay_card = ctk.CTkFrame(delay_shadow, fg_color=CARD_COLOR, corner_radius=16)
        delay_card.pack(fill="x", padx=3, pady=3)
        delay_top = ctk.CTkFrame(delay_card, fg_color=CARD_COLOR)
        delay_top.pack(fill="x", padx=20, pady=(16, 4))
        ctk.CTkLabel(delay_top, text="⏱ Trigger Delay",
            font=("Greater Theory", 13, "bold"),
            text_color=TEXT_PRIMARY).pack(side="left")
        self._delay_lbl = ctk.CTkLabel(delay_top, text=f"{self._delay:.1f}s",
            font=("Poppins", 13, "bold"),
            text_color=ACCENT_GREEN2)
        self._delay_lbl.pack(side="right")
        ctk.CTkSlider(delay_card, from_=0, to=15, number_of_steps=30,
            progress_color=ACCENT_GREEN2,
            button_color=ACCENT_GREEN2,
            button_hover_color=ACCENT_GREEN1,
            command=self._on_delay).pack(fill="x", padx=20, pady=(0, 16))

        # STATUS
        self._status_label = ctk.CTkLabel(main,
            text="✅ Status: Ready",
            font=("Poppins", 13),
            text_color=TEXT_SECONDARY)
        self._status_label.pack(anchor="w", padx=20, pady=16)

        # BUTTON
        shadow_button = ctk.CTkFrame(main, fg_color=SHADOW_COLOR, corner_radius=16)
        shadow_button.pack(fill="x", padx=3, pady=3)
        ctk.CTkButton(shadow_button, text="💨 Get Me Out",
            width=300, height=55, corner_radius=14,
            fg_color=ACCENT_GREEN2, hover_color=ACCENT_GREEN1,
            text_color=TEXT_PRIMARY,
            font=("Greater Theory", 18, "bold"),
            command=self._start_gmo).pack(fill="x", padx=3, pady=3)

    def _start_gmo(self):
        self._start_listener()
        self._update_status("🎙 Listening for keywords…")


#  Incoming Call Screen

    def show_incoming_call(self):
        if not self.state["gmo_active"]:
            return
        self._start_ringtone()

        for w in self.app.winfo_children():
            w.destroy()

        # resize to compact notification at top of screen
        self.app.geometry("650x130")
        screen_width = self.app.winfo_screenwidth()
        x = (screen_width - 650) // 2
        self.app.geometry(f"650x130+{x}+100")
        self.app.attributes('-topmost', True)

        main_frame = ctk.CTkFrame(self.app, fg_color=BG_COLOR)
        main_frame.pack(fill="both", expand=True, padx=0, pady=0)

        shadow_notification = ctk.CTkFrame(main_frame, fg_color=SHADOW_COLOR, corner_radius=20)
        shadow_notification.pack(fill="both", expand=True, padx=8, pady=8)

        notification_frame = ctk.CTkFrame(shadow_notification, fg_color=CARD_COLOR, corner_radius=18)
        notification_frame.pack(fill="both", expand=True, padx=4, pady=4)

        def play_audio():
           try:
               self._stop_ringtone()


               # use caller's preset audio if it exists, otherwise fall back to selected file
               preset = self._caller.get("audio", "")
               audio_path = preset if (preset and os.path.exists(preset)) else self.state["selected_mp3_path"]


               pygame.mixer.music.load(audio_path)
               pygame.mixer.music.play()
               self._accept_btn.configure(state="disabled")
               self._call_status.configure(text="Call Connected ✓")
               self._call_elapsed = 0
               self._tick_call()
           except FileNotFoundError:
               self._call_status.configure(text="Error: File not found!")
           except Exception as e:
               self._call_status.configure(text=f"Error: {str(e)}")

        def decline_call():
            self._stop_ringtone()
            pygame.mixer.music.stop()
            if self._listener:
                self._listener._triggered = False
            self.show_dashboard()

        left_frame = ctk.CTkFrame(notification_frame, fg_color=CARD_COLOR)
        left_frame.pack(side="left", fill="both", expand=True, padx=18, pady=18)

        # load caller image
        caller_image = self._load_caller_image(self.state["caller_image_path"])

        if caller_image:
            avatar_label = ctk.CTkLabel(left_frame, image=caller_image, text="")
        else:
            # fall back to initials avatar
            avatar_image = self._make_avatar(self._caller["name"])
            avatar_label = ctk.CTkLabel(left_frame, image=avatar_image, text="")

        avatar_label.pack(side="left", padx=(0, 18))

        text_frame = ctk.CTkFrame(left_frame, fg_color=CARD_COLOR)
        text_frame.pack(side="left", fill="both", expand=True)

        ctk.CTkLabel(text_frame, text=self._caller["name"],
            font=("Poppins", 16, "bold"),
            text_color=TEXT_PRIMARY).pack(anchor="w", padx=3)

        ctk.CTkLabel(text_frame, text=self._caller["number"],
            font=("Poppins", 13),
            text_color=TEXT_SECONDARY).pack(anchor="w", padx=3, pady=(2, 0))

        self._call_status = ctk.CTkLabel(text_frame, text="Incoming call…",
            font=("Poppins", 11),
            text_color=ACCENT_GREEN2)
        self._call_status.pack(anchor="w", padx=3)

        right_frame = ctk.CTkFrame(notification_frame, fg_color=CARD_COLOR)
        right_frame.pack(side="right", fill="both", padx=18, pady=12)

        self._accept_btn = ctk.CTkButton(right_frame, text="✓ Accept",
            width=100, height=38, corner_radius=10,
            fg_color=ACCENT_GREEN2, hover_color=ACCENT_GREEN1,
            text_color=TEXT_PRIMARY,
            font=("Poppins", 13, "bold"),
            command=play_audio)
        self._accept_btn.pack(pady=(0, 8))

        ctk.CTkButton(right_frame, text="✕ Decline",
            width=100, height=38, corner_radius=10,
            fg_color=ACCENT_RED, hover_color="#FF4A7F",
            text_color=TEXT_PRIMARY,
            font=("Poppins", 13, "bold"),
            command=decline_call).pack()

    def _tick_call(self):
        if not self._call_status or not self._call_status.winfo_exists():
            return
        self._call_elapsed += 1
        m, s = divmod(self._call_elapsed, 60)
        self._call_status.configure(text=f"Connected  {m}:{s:02d}")
        self.app.after(1000, self._tick_call)


# ==================== MAIN EXECUTION ====================

if __name__ == "__main__":
    GMOApp()