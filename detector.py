"""
Detection logic for Molloy Detector.

ScreenDetector:         Claude Vision API — no reference photo needed.
FaceRecognitionDetector: Local dlib face_recognition — free, fast, offline.
AudioDetector:          Google Speech transcription + keyword matching.
"""

import base64
import io

import anthropic
import numpy as np


# ── Shared screen capture ──────────────────────────────────────────────────

def capture_screen_pil(max_w=1280, max_h=720):
    """Returns a PIL Image of the primary monitor, resized to fit within max_w×max_h."""
    try:
        import mss
        from PIL import Image
        with mss.mss() as sct:
            shot = sct.grab(sct.monitors[1])
            img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
    except Exception:
        from PIL import ImageGrab
        img = ImageGrab.grab()
    img.thumbnail((max_w, max_h))
    return img


# ── Claude Vision detector ─────────────────────────────────────────────────

class ScreenDetector:
    PROMPT = (
        "Is the character Daniel Molloy from the AMC TV show 'Interview with the Vampire' (2022–) "
        "currently visible on screen? Daniel Molloy is a journalist who interviews Louis de Pointe du Lac. "
        "He is played by actor Eric Bogosian — a middle-aged man with gray/silver hair, often wearing "
        "casual-intellectual clothing and appearing in interview settings. "
        "Answer with only YES or NO."
    )

    def __init__(self):
        self.client = anthropic.Anthropic()

    def detect(self):
        """Returns (detected: bool, note: str)."""
        img = capture_screen_pil()
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=82)
        image_b64 = base64.b64encode(buf.getvalue()).decode()

        response = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=10,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/jpeg", "data": image_b64},
                    },
                    {"type": "text", "text": self.PROMPT},
                ],
            }],
        )
        answer = response.content[0].text.strip().upper()
        return answer.startswith("YES"), answer


# ── Local face recognition detector ───────────────────────────────────────

class FaceRecognitionDetector:
    """
    Compares every face found on screen against a pre-loaded reference photo.
    Runs entirely locally — no API calls, no cost.
    tolerance: 0.0 = identical, 1.0 = very loose. 0.55 is a good default.
    """

    def __init__(self, tolerance: float = 0.65):
        self.tolerance = tolerance
        self.reference_encoding = None
        self.reference_path: str | None = None

    def load_reference(self, image_path: str):
        """Load and encode a reference photo. Raises ValueError if no face is found."""
        import face_recognition
        img = face_recognition.load_image_file(image_path)
        encodings = face_recognition.face_encodings(img)
        if not encodings:
            raise ValueError("No face detected in the reference photo. Try a clearer, front-facing image.")
        self.reference_encoding = encodings[0]
        self.reference_path = image_path

    @property
    def ready(self) -> bool:
        return self.reference_encoding is not None

    def detect(self):
        """Returns (detected: bool, note: str)."""
        if not self.ready:
            return False, "No reference photo loaded"

        import face_recognition
        img = capture_screen_pil(max_w=960, max_h=540)  # smaller = faster
        frame = np.array(img)

        locations = face_recognition.face_locations(frame, model="hog")
        if not locations:
            return False, "No faces on screen"

        encodings = face_recognition.face_encodings(frame, locations)
        distances = face_recognition.face_distance([self.reference_encoding], encodings[0]) if encodings else []

        for enc in encodings:
            dist = face_recognition.face_distance([self.reference_encoding], enc)[0]
            if dist <= self.tolerance:
                return True, f"Match — distance {dist:.2f}"

        best = min(face_recognition.face_distance([self.reference_encoding], e)[0] for e in encodings)
        return False, f"{len(encodings)} face(s) found, best distance {best:.2f}"


# ── Audio detector ─────────────────────────────────────────────────────────

class AudioDetector:
    KEYWORDS = ["daniel", "molloy", "mr. molloy", "daniel molloy", "the journalist"]
    SAMPLE_RATE = 16000
    CHUNK_SECONDS = 5

    def record_chunk(self):
        import sounddevice as sd
        samples = int(self.SAMPLE_RATE * self.CHUNK_SECONDS)
        recording = sd.rec(samples, samplerate=self.SAMPLE_RATE, channels=1, dtype="int16")
        sd.wait()
        return recording.flatten().tobytes()

    def transcribe(self, audio_bytes: bytes) -> str:
        import speech_recognition as sr
        recognizer = sr.Recognizer()
        audio = sr.AudioData(audio_bytes, self.SAMPLE_RATE, 2)
        try:
            return recognizer.recognize_google(audio).lower()
        except sr.UnknownValueError:
            return ""
        except sr.RequestError as e:
            return f"[API error: {e}]"

    def detect(self):
        """Returns (detected: bool, transcript: str)."""
        audio_bytes = self.record_chunk()
        transcript = self.transcribe(audio_bytes)
        hit = bool(transcript) and any(kw in transcript for kw in self.KEYWORDS)
        return hit, transcript
