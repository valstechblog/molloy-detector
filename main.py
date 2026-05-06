#!/usr/bin/env python3
"""
Molloy Detector
Plays SexyBack by Justin Timberlake whenever Daniel Molloy
appears on screen or is referenced in detected audio.

Requirements: pip install -r requirements.txt
Sound file:   drop sexyback.mp3 into assets/
Reference:    load any clear photo of Daniel Molloy via the UI
"""

import os
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox

import sound_player
from detector import AudioDetector, FaceRecognitionDetector, ScreenDetector

# ── Palette ────────────────────────────────────────────────────────────────
BG       = "#0d0d1a"
PANEL_BG = "#14142b"
GOLD     = "#c9a84c"
GOLD_DIM = "#7a5f22"
RED      = "#cc2200"
RED_GLOW = "#ff4422"
GREEN    = "#44cc88"
SLATE    = "#3a3a5c"
WHITE    = "#e8e0d0"
LOG_BG   = "#0a0a14"

SCREEN_INTERVAL = 2   # seconds between screen captures
COOLDOWN        = 12  # seconds between sound triggers

THUMB_SIZE = (80, 80)

# ── App ────────────────────────────────────────────────────────────────────

class MolloyDetectorApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("MOLLOY DETECTOR")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)

        self.status_q: queue.Queue = queue.Queue()

        self.screen_running = False
        self.audio_running  = False
        self.screen_thread: threading.Thread | None = None
        self.audio_thread:  threading.Thread | None = None

        self.last_triggered = 0.0

        # Detectors — face detector is persistent so reference survives restarts
        self.face_detector = FaceRecognitionDetector(tolerance=0.55)
        self._thumb_photo   = None  # keep reference to avoid GC

        self._build_ui()
        self._check_sound_file()
        self._poll_queue()

    # ── UI Construction ────────────────────────────────────────────────────

    def _build_ui(self):
        title_f = tk.Frame(self.root, bg=BG)
        title_f.pack(pady=(22, 4))

        tk.Label(title_f, text="MOLLOY DETECTOR",
                 font=("Georgia", 26, "bold"), fg=GOLD, bg=BG).pack()
        tk.Label(title_f, text='"They\'ve come for you, Daniel."',
                 font=("Georgia", 11, "italic"), fg=GOLD_DIM, bg=BG).pack()

        # Detection pulse bar
        self.pulse_canvas = tk.Canvas(self.root, width=540, height=14,
                                      bg=BG, highlightthickness=0)
        self.pulse_canvas.pack(pady=(8, 0))
        self._pulse_bar = self.pulse_canvas.create_rectangle(
            0, 0, 540, 14, fill=SLATE, outline="")

        # Monitor panels side-by-side
        panels_f = tk.Frame(self.root, bg=BG)
        panels_f.pack(pady=14, padx=24)
        self._build_screen_panel(panels_f)
        self._build_audio_panel(panels_f)

        # Settings row
        settings_f = tk.Frame(self.root, bg=BG)
        settings_f.pack(pady=(0, 10), padx=24)

        tk.Label(settings_f, text="Play for:", fg=WHITE, bg=BG,
                 font=("Courier", 11)).grid(row=0, column=0, sticky="w")
        self.duration_var = tk.IntVar(value=10)
        tk.Spinbox(settings_f, from_=1, to=300, textvariable=self.duration_var,
                   width=4, font=("Courier", 11), bg=PANEL_BG, fg=GOLD,
                   buttonbackground=SLATE, relief="flat"
                   ).grid(row=0, column=1, padx=(6, 2))
        tk.Label(settings_f, text="sec", fg=WHITE, bg=BG,
                 font=("Courier", 11)).grid(row=0, column=2, sticky="w")

        tk.Label(settings_f, text="  Cooldown:", fg=WHITE, bg=BG,
                 font=("Courier", 11)).grid(row=0, column=3, sticky="w")
        self.cooldown_var = tk.IntVar(value=COOLDOWN)
        tk.Spinbox(settings_f, from_=2, to=120, textvariable=self.cooldown_var,
                   width=4, font=("Courier", 11), bg=PANEL_BG, fg=GOLD,
                   buttonbackground=SLATE, relief="flat"
                   ).grid(row=0, column=4, padx=(6, 2))
        tk.Label(settings_f, text="sec", fg=WHITE, bg=BG,
                 font=("Courier", 11)).grid(row=0, column=5, sticky="w")

        tk.Button(settings_f, text="▶  TEST", command=self._test_sound,
                  bg=SLATE, fg=GOLD, font=("Courier", 11, "bold"),
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  activebackground=GOLD, activeforeground=BG,
                  ).grid(row=0, column=6, padx=(20, 4))

        tk.Button(settings_f, text="⏹  STOP", command=self._stop_sound,
                  bg=SLATE, fg=RED_GLOW, font=("Courier", 11, "bold"),
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  activebackground=RED, activeforeground=WHITE,
                  ).grid(row=0, column=7, padx=(0, 0))

        # Log
        log_frame = tk.Frame(self.root, bg=BG)
        log_frame.pack(padx=24, pady=(0, 18), fill="x")

        tk.Label(log_frame, text="STATUS LOG", fg=GOLD_DIM, bg=BG,
                 font=("Courier", 9, "bold")).pack(anchor="w")

        log_inner = tk.Frame(log_frame, bg=BG)
        log_inner.pack(fill="x")

        self.log = tk.Text(
            log_inner, height=10, width=64,
            bg=LOG_BG, fg=WHITE, font=("Courier", 11),
            relief="flat", state="disabled", cursor="arrow",
            selectbackground=SLATE,
        )
        self.log.pack(side="left", fill="x", expand=True)

        scroll = tk.Scrollbar(log_inner, command=self.log.yview,
                              bg=PANEL_BG, troughcolor=BG)
        scroll.pack(side="right", fill="y")
        self.log.configure(yscrollcommand=scroll.set)

        self._log("Molloy Detector ready. Start a monitor to begin.")

    # ── Screen Panel ───────────────────────────────────────────────────────

    def _build_screen_panel(self, parent):
        f = tk.LabelFrame(parent, text="  📺  SCREEN MONITOR  ",
                          bg=PANEL_BG, fg=GOLD, font=("Georgia", 12, "bold"),
                          relief="flat", bd=2, labelanchor="n")
        f.grid(row=0, column=0, padx=(0, 10), sticky="nsew")

        # Mode toggle
        mode_f = tk.Frame(f, bg=PANEL_BG)
        mode_f.pack(pady=(10, 4))

        self.screen_mode_var = tk.StringVar(value="face")

        tk.Radiobutton(mode_f, text="Face Recognition  (free, local)",
                       variable=self.screen_mode_var, value="face",
                       bg=PANEL_BG, fg=WHITE, selectcolor=BG,
                       activebackground=PANEL_BG, font=("Courier", 10),
                       command=self._on_mode_change).pack(anchor="w")
        tk.Radiobutton(mode_f, text="Claude Vision  (~$4.80/hr)",
                       variable=self.screen_mode_var, value="claude",
                       bg=PANEL_BG, fg=WHITE, selectcolor=BG,
                       activebackground=PANEL_BG, font=("Courier", 10),
                       command=self._on_mode_change).pack(anchor="w")

        # Reference photo section (shown in face mode)
        self.ref_frame = tk.Frame(f, bg=PANEL_BG)
        self.ref_frame.pack(pady=(6, 4))

        self.load_btn = tk.Button(
            self.ref_frame, text="📂  Load Reference Photo",
            command=self._load_reference_photo,
            bg=SLATE, fg=WHITE, font=("Courier", 10),
            relief="flat", padx=8, pady=4, cursor="hand2",
            activebackground=GOLD, activeforeground=BG,
        )
        self.load_btn.pack()

        # Thumbnail canvas
        self.thumb_canvas = tk.Canvas(self.ref_frame, width=THUMB_SIZE[0],
                                      height=THUMB_SIZE[1], bg=BG,
                                      highlightthickness=1,
                                      highlightbackground=SLATE)
        self.thumb_canvas.pack(pady=(6, 0))
        self.thumb_canvas.create_text(
            THUMB_SIZE[0] // 2, THUMB_SIZE[1] // 2,
            text="no photo\nloaded", fill=SLATE, font=("Courier", 9),
            justify="center", tags="placeholder",
        )

        self.ref_label = tk.Label(self.ref_frame, text="", bg=PANEL_BG,
                                  fg=GREEN, font=("Courier", 9))
        self.ref_label.pack()

        # Status + start button
        self.face_info_lbl = tk.Label(f, text="", bg=PANEL_BG,
                                       fg=SLATE, font=("Courier", 10),
                                       justify="center")
        self.face_info_lbl.pack(pady=(6, 0))

        self.screen_status_lbl = tk.Label(f, text="● IDLE", bg=PANEL_BG,
                                          fg=SLATE, font=("Courier", 11, "bold"))
        self.screen_status_lbl.pack(pady=(2, 4))

        self.screen_btn = tk.Button(
            f, text="START MONITORING", command=self._toggle_screen,
            bg=SLATE, fg=WHITE, font=("Courier", 11, "bold"),
            relief="flat", padx=12, pady=6, cursor="hand2",
            activebackground=GREEN, activeforeground=BG,
        )
        self.screen_btn.pack(pady=(0, 14))

    def _on_mode_change(self):
        mode = self.screen_mode_var.get()
        if mode == "face":
            self.ref_frame.pack(pady=(6, 4))
        else:
            self.ref_frame.pack_forget()

    def _load_reference_photo(self):
        path = filedialog.askopenfilename(
            title="Select reference photo of Daniel Molloy",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.webp"), ("All", "*.*")],
        )
        if not path:
            return
        try:
            self.face_detector.load_reference(path)
            self._set_thumbnail(path)
            name = os.path.basename(path)
            self.ref_label.configure(text=f"✓ {name[:28]}")
            self._log(f"[FACE] Reference photo loaded: {name}")
        except Exception as e:
            messagebox.showerror("Face Load Error", str(e))
            self._log(f"[FACE ERROR] {e}")

    def _set_thumbnail(self, path: str):
        from PIL import Image, ImageTk
        img = Image.open(path).convert("RGB")
        img.thumbnail(THUMB_SIZE)
        self._thumb_photo = ImageTk.PhotoImage(img)
        self.thumb_canvas.delete("placeholder")
        self.thumb_canvas.create_image(
            THUMB_SIZE[0] // 2, THUMB_SIZE[1] // 2,
            image=self._thumb_photo,
        )

    # ── Audio Panel ────────────────────────────────────────────────────────

    def _build_audio_panel(self, parent):
        f = tk.LabelFrame(parent, text="  🎙  AUDIO MONITOR  ",
                          bg=PANEL_BG, fg=GOLD, font=("Georgia", 12, "bold"),
                          relief="flat", bd=2, labelanchor="n")
        f.grid(row=0, column=1, padx=(10, 0), sticky="nsew")

        tk.Label(f, text='Records 5-second clips and\ntranscribes via Google Speech.\nTriggers on "Daniel" / "Molloy".',
                 bg=PANEL_BG, fg=WHITE, font=("Courier", 10), justify="center",
                 ).pack(pady=(10, 8))

        self.audio_status_lbl = tk.Label(f, text="● IDLE", bg=PANEL_BG,
                                         fg=SLATE, font=("Courier", 11, "bold"))
        self.audio_status_lbl.pack(pady=(0, 8))

        self.audio_btn = tk.Button(
            f, text="START MONITORING", command=self._toggle_audio,
            bg=SLATE, fg=WHITE, font=("Courier", 11, "bold"),
            relief="flat", padx=12, pady=6, cursor="hand2",
            activebackground=GREEN, activeforeground=BG,
        )
        self.audio_btn.pack(pady=(0, 14))

    # ── Monitor Loops ──────────────────────────────────────────────────────

    def _screen_loop(self, detector):
        is_face_mode = isinstance(detector, FaceRecognitionDetector)
        while self.screen_running:
            try:
                self.status_q.put(("screen_status", "● Scanning…"))
                detected, note = detector.detect()

                if is_face_mode:
                    self.status_q.put(("face_info", note))

                if detected:
                    self.status_q.put(("screen_status", "● MOLLOY ON SCREEN"))
                    self.status_q.put(("log", f"[SCREEN] Detected! {note}"))
                    self.status_q.put(("trigger", None))
                else:
                    self.status_q.put(("screen_status", "● Scanning…"))
            except Exception as e:
                self.status_q.put(("screen_status", "● ERROR"))
                self.status_q.put(("face_info", ""))
                self.status_q.put(("log", f"[SCREEN ERROR] {e}"))

            # Interruptible sleep
            for _ in range(SCREEN_INTERVAL * 10):
                if not self.screen_running:
                    break
                time.sleep(0.1)

        self.status_q.put(("screen_done", None))

    def _audio_loop(self):
        detector = AudioDetector()
        while self.audio_running:
            try:
                self.status_q.put(("audio_status", "● Listening…"))
                detected, transcript = detector.detect()
                if detected:
                    self.status_q.put(("audio_status", "● MOLLOY HEARD"))
                    self.status_q.put(("log", f'[AUDIO] Keyword hit: "{transcript}"'))
                    self.status_q.put(("trigger", None))
                elif transcript:
                    short = transcript[:60] + ("…" if len(transcript) > 60 else "")
                    self.status_q.put(("log", f'[AUDIO] "{short}"'))
            except Exception as e:
                self.status_q.put(("audio_status", "● ERROR"))
                self.status_q.put(("log", f"[AUDIO ERROR] {e}"))

        self.status_q.put(("audio_done", None))

    # ── Toggle Handlers ────────────────────────────────────────────────────

    def _toggle_screen(self):
        if not self.screen_running:
            mode = self.screen_mode_var.get()
            if mode == "face":
                if not self.face_detector.ready:
                    messagebox.showwarning(
                        "No Reference Photo",
                        "Load a reference photo of Daniel Molloy first.",
                    )
                    return
                detector = self.face_detector
                self._log("[SCREEN] Starting — Face Recognition mode")
            else:
                detector = ScreenDetector()
                self._log("[SCREEN] Starting — Claude Vision mode")

            self.screen_running = True
            self.screen_btn.configure(text="STOP MONITORING", bg=RED)
            self.screen_status_lbl.configure(fg=GREEN, text="● Starting…")
            self.screen_thread = threading.Thread(
                target=self._screen_loop, args=(detector,), daemon=True)
            self.screen_thread.start()
        else:
            self.screen_running = False
            self.screen_btn.configure(text="START MONITORING", bg=SLATE)
            self._log("[SCREEN] Monitor stopping…")

    def _toggle_audio(self):
        if not self.audio_running:
            self.audio_running = True
            self.audio_btn.configure(text="STOP MONITORING", bg=RED)
            self.audio_status_lbl.configure(fg=GREEN, text="● Starting…")
            self._log("[AUDIO] Monitor started")
            self.audio_thread = threading.Thread(
                target=self._audio_loop, daemon=True)
            self.audio_thread.start()
        else:
            self.audio_running = False
            self.audio_btn.configure(text="START MONITORING", bg=SLATE)
            self._log("[AUDIO] Monitor stopping…")

    # ── Queue Processing ───────────────────────────────────────────────────

    def _poll_queue(self):
        try:
            while True:
                kind, value = self.status_q.get_nowait()
                if kind == "log":
                    self._log(value)
                elif kind == "face_info":
                    self._update_face_info(value)
                elif kind == "screen_status":
                    color = RED_GLOW if "MOLLOY" in value else (GREEN if "Scan" in value else SLATE)
                    self.screen_status_lbl.configure(text=value, fg=color)
                elif kind == "audio_status":
                    color = RED_GLOW if "MOLLOY" in value else (GREEN if "Listen" in value else SLATE)
                    self.audio_status_lbl.configure(text=value, fg=color)
                elif kind == "trigger":
                    self._trigger()
                elif kind == "screen_done":
                    self.screen_btn.configure(text="START MONITORING", bg=SLATE)
                    self.screen_status_lbl.configure(text="● IDLE", fg=SLATE)
                    self.face_info_lbl.configure(text="", fg=SLATE)
                elif kind == "audio_done":
                    self.audio_btn.configure(text="START MONITORING", bg=SLATE)
                    self.audio_status_lbl.configure(text="● IDLE", fg=SLATE)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)

    # ── Trigger & Flash ────────────────────────────────────────────────────

    def _trigger(self):
        now = time.time()
        cooldown = self.cooldown_var.get()
        if now - self.last_triggered < cooldown:
            remaining = cooldown - (now - self.last_triggered)
            self._log(f"[TRIGGER] On cooldown — {remaining:.0f}s remaining")
            return
        self.last_triggered = now
        duration = self.duration_var.get()
        self._log(f"🎵  MOLLOY DETECTED — IT'S SEXY TIME  🎵  (playing {duration}s)")
        sound_player.play(duration=duration)
        self._flash_pulse(0)

    def _flash_pulse(self, step: int):
        colors = [RED_GLOW, GOLD, RED_GLOW, GOLD, RED_GLOW, GOLD, SLATE]
        if step < len(colors):
            self.pulse_canvas.itemconfigure(self._pulse_bar, fill=colors[step])
            self.root.after(120, lambda: self._flash_pulse(step + 1))
        else:
            self.pulse_canvas.itemconfigure(self._pulse_bar, fill=SLATE)

    # ── Helpers ────────────────────────────────────────────────────────────

    def _update_face_info(self, note: str):
        """Translate a detector note into a human-readable face indicator."""
        if not note or "No faces" in note or "No reference" in note:
            self.face_info_lbl.configure(text="👤  no faces on screen", fg=SLATE)
        elif "Match" in note:
            self.face_info_lbl.configure(text=f"🟢  {note}", fg=GREEN)
        else:
            # e.g. "2 face(s) found, best distance 0.72"
            self.face_info_lbl.configure(text=f"👤  {note}", fg=GOLD)

    def _test_sound(self):
        duration = self.duration_var.get()
        self._log(f"[TEST] Playing sound for {duration}s…")
        self._flash_pulse(0)
        sound_player.play(duration=duration)

    def _stop_sound(self):
        sound_player.stop()
        self._log("[STOP] Sound stopped manually")

    def _log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self.log.configure(state="normal")
        self.log.insert("end", f"[{ts}]  {msg}\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _check_sound_file(self):
        if not os.path.exists(sound_player.SOUND_PATH):
            self._log("⚠  No sound file at assets/sexyback.mp3 — will use system beep.")


# ── Entry point ────────────────────────────────────────────────────────────

def main():
    root = tk.Tk()
    app = MolloyDetectorApp(root)

    root.update_idletasks()
    w, h = root.winfo_width(), root.winfo_height()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")

    root.mainloop()


if __name__ == "__main__":
    main()
