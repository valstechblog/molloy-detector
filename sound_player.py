"""Sound playback for Molloy Detector."""

import os
import subprocess
import threading
import time

SOUND_PATH = os.path.join(os.path.dirname(__file__), "assets", "sexyback.mp3")

_mixer_ready = False
_afplay_proc: subprocess.Popen | None = None
_stop_timer:  threading.Timer | None = None


def _init_pygame():
    global _mixer_ready
    if not _mixer_ready:
        try:
            import pygame
            pygame.mixer.init()
            _mixer_ready = True
        except Exception:
            pass


def play(path=SOUND_PATH, duration: float = 10.0):
    """Play audio file, auto-stopping after `duration` seconds."""
    stop()  # cancel anything already playing

    def _play():
        global _afplay_proc, _stop_timer

        if os.path.exists(path):
            _init_pygame()
            if _mixer_ready:
                try:
                    import pygame
                    pygame.mixer.music.load(path)
                    pygame.mixer.music.play()
                    _stop_timer = threading.Timer(duration, stop)
                    _stop_timer.daemon = True
                    _stop_timer.start()
                    return
                except Exception:
                    pass
            # pygame unavailable — use afplay (macOS)
            try:
                _afplay_proc = subprocess.Popen(["afplay", path])
                _stop_timer = threading.Timer(duration, stop)
                _stop_timer.daemon = True
                _stop_timer.start()
                return
            except FileNotFoundError:
                pass

        # No sound file — system alert (brief, no timer needed)
        try:
            subprocess.Popen(["afplay", "/System/Library/Sounds/Glass.aiff"])
        except Exception:
            pass

    threading.Thread(target=_play, daemon=True).start()


def stop():
    """Stop playback immediately and cancel any pending auto-stop timer."""
    global _afplay_proc, _stop_timer

    if _stop_timer is not None:
        _stop_timer.cancel()
        _stop_timer = None

    if _mixer_ready:
        try:
            import pygame
            pygame.mixer.music.stop()
        except Exception:
            pass

    if _afplay_proc is not None:
        try:
            _afplay_proc.terminate()
        except Exception:
            pass
        _afplay_proc = None
