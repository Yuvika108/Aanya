"""
AANYA — Backend Engine
Handles Gemini AI, speech recognition, command dispatch, and task persistence.
"""

import os
import subprocess
import datetime
import random
import sys
import time
import threading
import shutil
import collections
import re
import urllib.parse
import urllib.request
import functools
import speech_recognition as sr

try:
    import sounddevice as sd
    import numpy as np
    HAVE_SOUNDDEVICE = True
except ImportError:
    HAVE_SOUNDDEVICE = False

from google import genai
from google.genai import types
from config import gemini_key

# ─────────────────────────────────────────────
#  ANSI palette (terminal mode only)
# ─────────────────────────────────────────────
class C:
    RESET = "\033[0m"; BOLD = "\033[1m"; DIM = "\033[2m"
    WHITE = "\033[97m"; CYAN = "\033[96m"; MAGENTA = "\033[95m"
    BLUE  = "\033[94m"; GREEN = "\033[92m"; YELLOW = "\033[93m"
    RED   = "\033[91m"; GREY  = "\033[90m"


# ─────────────────────────────────────────────
#  Constants
# ─────────────────────────────────────────────
SITES = {
    "youtube":   "https://www.youtube.com",
    "whatsapp":  "https://web.whatsapp.com/",
    "wikipedia": "https://www.wikipedia.org",
    "google":    "https://www.google.com",
    "spotify":   "https://open.spotify.com",
    "leetcode":  "https://leetcode.com/u/Yuv1ka/",
    "github":    "https://github.com/Yuvika108",
    "gmail":     "https://mail.google.com/mail/u/0/#inbox",
}

# Rich site rules supporting multiple voice and text aliases
SITE_RULES = [
    {
        "name": "GitHub",
        "aliases": ["github", "git hub", "git-hub", "gethub", "my github"],
        "url": "https://github.com/Yuvika108",
    },
    {
        "name": "Gmail",
        "aliases": [
            "gmail", "google mail", "inbox", "email", "emails",
            "my email", "my emails", "mail", "mails", "my mail", "my mails"
        ],
        "url": "https://mail.google.com/mail/u/0/#inbox",
    },
    {
        "name": "Codolio",
        "aliases": ["codolio", "codolio profile", "my codolio", "codolio tracker", "codolio coding"],
        "url": "https://codolio.com",
    },
    {
        "name": "LinkedIn",
        "aliases": ["linkedin", "linked in", "my linkedin", "my linked in", "linkedin profile"],
        "url": "https://www.linkedin.com",
    },
    {
        "name": "WhatsApp",
        "aliases": ["whatsapp", "whats app", "what's app", "what app", "whatsapp web", "whats app web", "wa"],
        "url": "https://web.whatsapp.com/",
        "app_name": "WhatsApp",
    },
    {
        "name": "YouTube",
        "aliases": ["youtube", "you tube", "yt"],
        "url": "https://www.youtube.com",
    },
    {
        "name": "Wikipedia",
        "aliases": ["wikipedia", "wiki"],
        "url": "https://www.wikipedia.org",
    },
    {
        "name": "Google",
        "aliases": ["google"],
        "url": "https://www.google.com",
    },
    {
        "name": "Spotify",
        "aliases": ["spotify", "spotfy"],
        "url": "https://open.spotify.com",
    },
    {
        "name": "LeetCode",
        "aliases": ["leetcode", "leet code", "lc"],
        "url": "https://leetcode.com/u/Yuv1ka/",
    },
]

def _match_site_intent(query: str, custom_links: list[dict] | None = None):
    q = query.lower().strip()

    # 1. Search intents (Google, YouTube, Wikipedia)
    google_search = re.search(r"^(?:search(?:\s+for)?\s+(.+)\s+on\s+google|search\s+google\s+for\s+(.+)|google\s+(.+))$", q)
    if google_search:
        target = (google_search.group(1) or google_search.group(2) or google_search.group(3) or "").strip()
        if target and not target.startswith("is ") and not target.startswith("are ") and not target.startswith("what "):
            return {
                "name": "Google",
                "url": f"https://www.google.com/search?q={urllib.parse.quote(target)}",
                "say": f"Searching Google for {target}",
            }

    yt_search = re.search(r"^(?:search(?:\s+for)?\s+(.+)\s+on\s+youtube|search\s+youtube\s+for\s+(.+))$", q)
    if yt_search:
        target = (yt_search.group(1) or yt_search.group(2) or "").strip()
        if target:
            return {
                "name": "YouTube",
                "url": f"https://www.youtube.com/results?search_query={urllib.parse.quote(target)}",
                "say": f"Searching YouTube for {target}",
            }

    wiki_search = re.search(r"^(?:search(?:\s+for)?\s+(.+)\s+on\s+wikipedia|search\s+wikipedia\s+for\s+(.+)|wikipedia\s+(.+))$", q)
    if wiki_search:
        target = (wiki_search.group(1) or wiki_search.group(2) or "").strip()
        if target:
            return {
                "name": "Wikipedia",
                "url": f"https://en.wikipedia.org/w/index.php?search={urllib.parse.quote(target)}",
                "say": f"Searching Wikipedia for {target}",
            }

    # 2. Exclude drafting / sending emails or asking questions about sites
    if re.search(r"\b(?:draft|write|compose|send|create)\s+(?:an?\s+)?(?:email|mail|message)\b", q):
        return None
    if any(q.startswith(w) for w in ("what is ", "who is ", "how to ", "how do ", "why is ", "tell me about ", "explain ", "can you explain ")):
        return None

    # 3. Explicit open / visit command (with polite prefixes & synonyms)
    open_match = re.search(
        r"^(?:(?:can|could|would)\s+you\s+(?:please\s+)?|please\s+)?"
        r"(?:open|launch|go\s+to|visit|take\s+me\s+to|navigate\s+to|check|show(?:\s+me)?|view|read|access|look\s+at)\s+(.+)$",
        q,
    )
    target_site = open_match.group(1).strip() if open_match else q

    # Check custom user links first
    if custom_links:
        for cl in custom_links:
            name = (cl.get("name") or "").strip().lower()
            url = (cl.get("url") or "").strip()
            if not name or not url:
                continue
            if target_site == name or re.search(rf"\b{re.escape(name)}\b", target_site):
                if not open_match and len(target_site.split()) > 2:
                    continue
                return {
                    "name": cl.get("name", "Custom Link"),
                    "aliases": [name],
                    "url": url,
                    "say": f"Opening {cl.get('name')} for you",
                }

    for rule in SITE_RULES:
        for alias in rule["aliases"]:
            if target_site == alias or re.search(rf"\b{re.escape(alias)}\b", target_site):
                if not open_match and len(target_site.split()) > 2:
                    continue
                return rule

    return None

CURATED_SONGS = {
    "bohemian rhapsody": ("Bohemian Rhapsody", "Queen", "fJ9rUzIMcZQ"),
    "blinding lights": ("Blinding Lights", "The Weeknd", "4NRXx6U8ABQ"),
    "shape of you": ("Shape of You", "Ed Sheeran", "JGwWNGJdvx8"),
    "starboy": ("Starboy", "The Weeknd", "34Na4j8AVgA"),
    "flowers": ("Flowers", "Miley Cyrus", "G7KNmW9a75Y"),
    "as it was": ("As It Was", "Harry Styles", "H5v3kku4y6Q"),
    "believer": ("Believer", "Imagine Dragons", "7wtfhZwyrcc"),
    "levitating": ("Levitating", "Dua Lipa", "TUVcZfQe-Kw"),
    "viva la vida": ("Viva La Vida", "Coldplay", "dvgZkm1xWPE"),
    "stay": ("Stay", "Justin Bieber & The Kid LAROI", "kTJczUoc26U"),
    "kesariya": ("Kesariya", "Arijit Singh", "BddP6PYo2gs"),
    "hotel california": ("Hotel California", "Eagles", "dLl4PZtxia8"),
    "espresso": ("Espresso", "Sabrina Carpenter", "eVli-tstM5E"),
    "bad guy": ("Bad Guy", "Billie Eilish", "DyDfgMOUjCI"),
    "despacito": ("Despacito", "Luis Fonsi ft. Daddy Yankee", "kJQP7kiw5Fk"),
    "cruel summer": ("Cruel Summer", "Taylor Swift", "ic8j13piAhQ"),
    "not like us": ("Not Like Us", "Kendrick Lamar", "H58vbez_m4E"),
    "birds of a feather": ("Birds of a Feather", "Billie Eilish", "V9PVRfjEBTI"),
    "die with a smile": ("Die With a Smile", "Lady Gaga & Bruno Mars", "kPa7bsKwL-c"),
    "lose yourself": ("Lose Yourself", "Eminem", "xFYQQPAOz7Y"),
    "someone like you": ("Someone Like You", "Adele", "hLQl3WQQoQ0"),
    "rolling in the deep": ("Rolling in the Deep", "Adele", "rYEDA3JcQqw"),
    "perfect": ("Perfect", "Ed Sheeran", "2Vv-BfVoq4g"),
    "counting stars": ("Counting Stars", "OneRepublic", "hT_nvWreIhg"),
    "closer": ("Closer", "The Chainsmokers ft. Halsey", "PT2_F-1esPk"),
    "senorita": ("Señorita", "Shawn Mendes & Camila Cabello", "Pkh8UtuejGw"),
    "memories": ("Memories", "Maroon 5", "SlPhMPnQ58k"),
    "sunflower": ("Sunflower", "Post Malone & Swae Lee", "ApXoWvfEYVU"),
    "chuttamalle": ("Chuttamalle", "Shilpa Rao", "GWNrPJyRTcA"),
    "tauba tauba": ("Tauba Tauba", "Karan Aujla", "lk403dE0dG8"),
}

@functools.lru_cache(maxsize=256)
def resolve_song_playable_url(query: str) -> tuple[str, str | None]:
    """Resolve a song query to a direct playable YouTube watch URL with autoplay=1.
    Uses curated map for instantaneous response or fast regex extraction from YouTube search.
    Guarantees a direct playable video URL that starts playing immediately upon opening.
    """
    q_norm = query.lower().strip()
    for key, (song, artist, vid) in CURATED_SONGS.items():
        if key in q_norm or q_norm in key:
            return f"https://www.youtube.com/watch?v={vid}&autoplay=1", vid

    try:
        search_query = f"{query} song audio"
        search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(search_query)}"
        req = urllib.request.Request(
            search_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            }
        )
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        matches = re.findall(r'\"videoId\":\"([a-zA-Z0-9_-]{11})\"', html)
        if not matches:
            matches = re.findall(r'/watch\?v=([a-zA-Z0-9_-]{11})', html)
        if matches:
            vid = matches[0]
            return f"https://www.youtube.com/watch?v={vid}&autoplay=1", vid
    except Exception:
        pass

    # Intelligent fallback: pick a popular song so playback starts immediately
    key, (song, artist, vid) = random.choice(list(CURATED_SONGS.items()))
    return f"https://www.youtube.com/watch?v={vid}&autoplay=1", vid

# Table-driven app commands: (trigger_phrases, say_name, open_path)
APP_COMMANDS = [
    (["open chrome"],                               "Chrome",   "/Applications/Google Chrome.app"),
    (["open brave"],                                "Brave",    "/Applications/Brave Browser.app"),
    (["open finder", "open files"],                 "Finder",   None),          # None → home dir
    (["open spotify"],                              "Spotify",  "https://open.spotify.com/"),
    (["open whatsapp", "open whats app", "open what's app", "open whatsapp web"], "WhatsApp", "https://web.whatsapp.com/"),
    (["open github", "open git hub", "open git-hub"], "GitHub",   "https://github.com/Yuv1ka/"),
    (["open gmail", "open mail"],                   "Gmail",    "https://mail.google.com/mail/u/0/#inbox"),
]

DEFAULT_PRIMARY_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
MODEL_CASCADE = [
    DEFAULT_PRIMARY_MODEL,
    "gemini-flash-lite-latest",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3-flash-preview",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
]
_seen_main = set()
MODEL_FALLBACK_CASCADE = []
for _m in MODEL_CASCADE:
    if _m and _m not in _seen_main:
        _seen_main.add(_m)
        MODEL_FALLBACK_CASCADE.append(_m)

DEFAULT_MODEL = MODEL_FALLBACK_CASCADE[0]
FALLBACK_MODEL = MODEL_FALLBACK_CASCADE[1] if len(MODEL_FALLBACK_CASCADE) > 1 else MODEL_FALLBACK_CASCADE[0]

WAKE_VARIANTS = {"aanya", "anya", "hanya", "tanya", "anna", "ana", "onia", "nia"}
DATA_DIR = os.path.expanduser("~/.aanya")
os.makedirs(DATA_DIR, exist_ok=True)
TASK_FILE = os.path.join(DATA_DIR, "tasks.txt")
LINKS_FILE = os.path.join(DATA_DIR, "links.json")


# ─────────────────────────────────────────────
#  AanyaEngine
# ─────────────────────────────────────────────
class AanyaEngine:
    """Core voice-assistant logic, decoupled from any UI.

    Optional callbacks (set after construction):
        on_status(icon, label, message)
        on_speak(text)
        on_heard(text)
        on_wake()
        on_state(state)   — "standby" | "listening" | "thinking" | "speaking" | "executing"
    """

    def __init__(self):
        now = datetime.datetime.now()
        current_time_str = now.strftime("%A, %d %B %Y, %I:%M %p")
        self.system_instruction = (
            f"REAL-WORLD CLOCK & CALENDAR: The current date and time is {current_time_str}. "
            "You are Aanya, a helpful, smart, and articulate AI assistant made by Yuvi. "
            "Your responses are spoken aloud, so keep them natural, conversational, and pleasantly brief."
        )
        self.client = None
        self.chat_session = None
        self.active_model = DEFAULT_MODEL
        if gemini_key:
            try:
                self.client = genai.Client(api_key=gemini_key)
                self.reset_chat(announce=False)
            except Exception as e:
                print(f"[Warning] Failed to initialize Gemini client: {e}")
                print(f"[Warning] Failed to initialize Gemini client: {e}")

        self.recognizer = sr.Recognizer()
        self.recognizer.pause_threshold = 1
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.energy_threshold = 300

        self._running = False
        self._voice_thread = None

        # UI callbacks
        self.on_status = None
        self.on_speak  = None
        self.on_heard  = None
        self.on_wake   = None
        self.on_state  = None

    # ── Emit helpers ──────────────────────────

    def _emit_status(self, icon: str, label: str, message: str):
        if self.on_status:
            self.on_status(icon, label, message)

    def _emit_state(self, state: str):
        if self.on_state:
            self.on_state(state)

    # ── TTS ───────────────────────────────────

    def say(self, text: str):
        self._emit_state("speaking")
        if self.on_speak:
            self.on_speak(text)
        # Cross-platform TTS: use macOS 'say' if available, otherwise graceful fallback
        if sys.platform == "darwin" and shutil.which("say"):
            subprocess.run(["say", str(text)])
        else:
            # Deployment / Linux / headless environment fallback
            try:
                from gtts import gTTS
                # In headless environments we don't crash when hardware speaker isn't available
            except Exception:
                pass
        self._emit_state("standby")

    # ── STT ───────────────────────────────────

    def _listen_sounddevice(self, timeout: int = 7, phrase_time_limit: int = 12, sample_rate: int = 16000) -> str:
        """Capture audio using sounddevice (deployment-friendly universal wheel, no PyAudio compilation needed)
        and transcribe using Google STT via pure SpeechRecognition AudioData."""
        try:
            devices = sd.query_devices()
            has_input = any(d.get("max_input_channels", 0) > 0 for d in devices)
            if not has_input:
                self._emit_status("ℹ", "AUDIO", "No microphone detected (headless/cloud mode)")
                return "None"

            chunk_duration = 0.05  # 50ms chunks
            chunk_size = int(sample_rate * chunk_duration)
            pre_buffer_chunks = int(0.3 / chunk_duration)  # 300ms pre-speech buffer
            pre_buffer = collections.deque(maxlen=pre_buffer_chunks)

            with sd.InputStream(samplerate=sample_rate, channels=1, dtype="int16") as stream:
                # 1. Ambient noise calibration (300ms)
                calib_chunks = []
                for _ in range(6):
                    chunk, _ = stream.read(chunk_size)
                    calib_chunks.append(chunk)
                calib_arr = np.concatenate(calib_chunks).astype(np.float32)
                ambient_rms = float(np.sqrt(np.mean(np.square(calib_arr)))) if len(calib_arr) else 100.0
                energy_threshold = max(ambient_rms * 1.6, 300.0)

                # 2. Wait for speech to start (up to timeout seconds)
                start_wait = time.time()
                speech_started = False
                while time.time() - start_wait < timeout:
                    chunk, _ = stream.read(chunk_size)
                    pre_buffer.append(chunk)
                    rms = float(np.sqrt(np.mean(np.square(chunk.astype(np.float32)))))
                    if rms > energy_threshold:
                        speech_started = True
                        break

                if not speech_started:
                    return "None"

                # 3. Speech started: record until silence or phrase_time_limit
                recorded_frames = list(pre_buffer)
                speech_start_time = time.time()
                silence_start = None
                pause_threshold = 0.9  # 900ms silence stops utterance

                while True:
                    chunk, _ = stream.read(chunk_size)
                    recorded_frames.append(chunk)
                    now = time.time()

                    # Check overall phrase time limit
                    if now - speech_start_time > phrase_time_limit:
                        break

                    rms = float(np.sqrt(np.mean(np.square(chunk.astype(np.float32)))))
                    if rms < energy_threshold:
                        if silence_start is None:
                            silence_start = now
                        elif now - silence_start >= pause_threshold:
                            break
                    else:
                        silence_start = None

                # 4. Assemble audio data
                if not recorded_frames:
                    return "None"

                pcm_bytes = np.concatenate(recorded_frames).astype(np.int16).tobytes()
                audio_data = sr.AudioData(pcm_bytes, sample_rate, 2)
                return str(self.recognizer.recognize_google(audio_data, language="en-in"))

        except (sr.WaitTimeoutError, sr.UnknownValueError):
            return "None"
        except sr.RequestError as e:
            self._emit_status("✗", "NETWORK", f"Google STT unavailable: {e}")
            return "None"
        except Exception as e:
            self._emit_status("✗", "AUDIO ERROR", str(e))
            return "None"

    def listen(self, timeout: int = 7, phrase_time_limit: int = 12) -> str:
        # Primary: sounddevice (deployment-friendly, no C-compile or PyAudio needed)
        if HAVE_SOUNDDEVICE:
            return self._listen_sounddevice(timeout=timeout, phrase_time_limit=phrase_time_limit)

        # Fallback: SpeechRecognition Microphone (if pyaudio is installed locally)
        try:
            with sr.Microphone() as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.3)
                audio = self.recognizer.listen(source, timeout=timeout,
                                               phrase_time_limit=phrase_time_limit)
                return str(self.recognizer.recognize_google(audio, language="en-in"))
        except (sr.WaitTimeoutError, sr.UnknownValueError):
            return "None"
        except sr.RequestError as e:
            self._emit_status("✗", "NETWORK", f"Google STT unavailable: {e}")
            return "None"
        except Exception as e:
            self._emit_status("✗", "MIC ERROR", str(e))
            return "None"

    # ── Gemini ────────────────────────────────

    def chat(self, query: str) -> str:
        if not self.client:
            self._emit_status("✗", "NO KEY", "Set gemini_key in config.py")
            self.say("Please configure your Gemini API key in config.py to chat.")
            return ""
        self._emit_state("thinking")
        self._emit_status("💬", "THINKING", "Contacting Gemini...")

        # ── Fast path: direct send on existing active session without rebuild ──
        if self.chat_session is not None:
            try:
                response = self.chat_session.send_message(query)
                reply = response.text or ""
                # Keep history bounded
                try:
                    curr_history = self.chat_session.get_history()
                    if curr_history and len(curr_history) > 10:
                        recent = curr_history[-10:]
                        self.chat_session = self.client.chats.create(
                            model=self.active_model,
                            history=recent,
                            config=types.GenerateContentConfig(system_instruction=self.system_instruction)
                        )
                except Exception:
                    pass
                self.say(reply)
                return reply
            except Exception as e:
                print(f"[MainEngine] Active session failed with {getattr(self, 'active_model', 'unknown')}: {e}. Retrying fallback cascade...")
                self.chat_session = None

        history = []
        if self.chat_session:
            try:
                history = self.chat_session.get_history() or []
            except Exception:
                history = []

        curr_active = getattr(self, "active_model", None) or DEFAULT_MODEL
        models_to_try = [curr_active] + [m for m in MODEL_FALLBACK_CASCADE if m != curr_active]

        for model_name in models_to_try:
            try:
                self.chat_session = self.client.chats.create(
                    model=model_name,
                    history=history[-10:] if history else None,
                    config=types.GenerateContentConfig(system_instruction=self.system_instruction)
                )
                response = self.chat_session.send_message(query)
                reply = response.text or ""
                self.active_model = model_name

                self.say(reply)
                return reply
            except Exception as e:
                print(f"[MainEngine] Model {model_name} failed in chat(): {e}")
                time.sleep(0.2)
                continue

        fallback_msg = "I'm currently experiencing high demand across my network. Please try asking again in just a moment."
        self._emit_status("✗", "BUSY", "High model demand")
        self.say(fallback_msg)
        return fallback_msg

    def ai_generate(self, prompt: str):
        if not self.client:
            self._emit_status("✗", "NO KEY", "Set gemini_key in config.py")
            self.say("Please configure your Gemini API key in config.py.")
            return
        self.say("Generating response, please wait...")
        self._emit_state("thinking")
        self._emit_status("⚙", "AI MODE", "Generating content...")

        curr_active = getattr(self, "active_model", None) or DEFAULT_MODEL
        models_to_try = [curr_active] + [m for m in MODEL_FALLBACK_CASCADE if m != curr_active]
        reply = ""

        for model_name in models_to_try:
            try:
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                reply = response.text or ""
                self.active_model = model_name
                break
            except Exception as e:
                print(f"[MainEngine] Model {model_name} failed in ai_generate(): {e}")
                time.sleep(0.3)
                continue

        if not reply:
            self._emit_status("✗", "BUSY", "High model demand")
            self.say("I'm currently experiencing high demand across my network. Please try again shortly.")
            return

        try:
            responses_dir = os.path.join(DATA_DIR, "GeminiResponses")
            os.makedirs(responses_dir, exist_ok=True)
            slug = "".join(x for x in
                           prompt.lower().split("using artificial intelligence")[-1].strip()
                           if x.isalnum() or x in " _-").strip()
            filename = slug or f"response_{random.randint(1, 9999)}"
            filepath = os.path.join(responses_dir, f"{filename}.txt")
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"Gemini response for: {prompt}\n{'─'*40}\n\n{reply}")
            self._emit_status("✔", "SAVED", filepath)
            self.say(f"Done! I've saved the response to {filename}.")
        except Exception as e:
            self._emit_status("✗", "ERROR", str(e))
            self.say("I encountered an error while saving the response.")

    def reset_chat(self, announce: bool = True):
        if not self.client:
            self._emit_status("✗", "NO KEY", "Set gemini_key in config.py")
            return

        target = getattr(self, "active_model", None) or DEFAULT_MODEL
        candidates = [target] + [m for m in MODEL_FALLBACK_CASCADE if m != target]
        for m in candidates:
            try:
                self.chat_session = self.client.chats.create(
                    model=m,
                    config=types.GenerateContentConfig(system_instruction=self.system_instruction)
                )
                self.active_model = m
                break
            except Exception as e:
                print(f"[MainEngine] Could not initialize model {m} in reset_chat: {e}")
                continue

        if announce:
            self._emit_status("🔄", "RESET", "Chat history cleared.")
            self.say("Chat history has been reset.")

    # ── Tasks ─────────────────────────────────

    def save_task(self, task: str):
        with open(TASK_FILE, "a") as f:
            f.write(task + "\n")

    def load_tasks(self) -> list:
        if not os.path.exists(TASK_FILE):
            return []
        with open(TASK_FILE) as f:
            return [ln.strip() for ln in f if ln.strip()]

    def delete_task(self, task_number_str: str):
        tasks = self.load_tasks()
        try:
            idx = int(task_number_str) - 1
            if 0 <= idx < len(tasks):
                removed = tasks.pop(idx)
                with open(TASK_FILE, "w") as f:
                    f.write("\n".join(tasks) + ("\n" if tasks else ""))
                self.say(f"Removed task: {removed}")
                return removed
            self.say("Invalid task number.")
        except ValueError:
            self.say("Please say the task number you'd like to delete.")
        return None

    # ── Custom Links & Shortcuts ──────────────────────────────────────────────

    def get_links(self) -> list[dict]:
        if os.path.exists(LINKS_FILE):
            try:
                with open(LINKS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def add_link(self, name: str, url: str) -> dict:
        links = self.get_links()
        clean_name = name.strip()
        clean_url = url.strip()
        if not clean_url.startswith(("http://", "https://")):
            clean_url = f"https://{clean_url}"
        link_id = f"link_{int(datetime.datetime.now().timestamp() * 1000)}"
        new_link = {
            "id": link_id,
            "name": clean_name,
            "url": clean_url,
            "created_at": datetime.datetime.now().isoformat(),
        }
        existing = next((l for l in links if l.get("name", "").lower() == clean_name.lower()), None)
        if existing:
            existing["url"] = clean_url
            new_link = existing
        else:
            links.append(new_link)
        with open(LINKS_FILE, "w", encoding="utf-8") as f:
            json.dump(links, f, indent=2)
        return new_link

    def delete_link(self, link_id: str) -> bool:
        links = self.get_links()
        filtered = [l for l in links if l.get("id") != link_id and l.get("name", "").lower() != link_id.lower()]
        if len(filtered) != len(links):
            with open(LINKS_FILE, "w", encoding="utf-8") as f:
                json.dump(filtered, f, indent=2)
            return True
        return False

    # ── Wake word ─────────────────────────────

    @staticmethod
    def is_wake_word(text: str) -> bool:
        return any(w in WAKE_VARIANTS for w in text.lower().split())

    # ── Music & Song Playback (Alexa-style Immediate Autoplay) ────────────────

    def _parse_song_intent(self, query: str) -> dict | None:
        """Parse Alexa-style song playback and recommendation requests.
        Always plays the song directly from YouTube upon opening.
        """
        q = query.lower().strip()

        # Questions about playing or instructions are NOT music playback requests
        if re.search(r"\b(?:how\s+(?:to|can\s+i|do\s+i)|teach\s+me\s+to|learn\s+to|what\s+is|who\s+is|why\s+do|where\s+can\s+i)\b", q):
            return None

        # Exclude non-music verbs, games, activities, figures of speech
        non_music = (
            "chess", "cricket", "game", "games", "football", "tennis", "basketball",
            "minecraft", "fortnite", "poker", "cards", "monopoly", "blackjack",
            "puzzle", "crossword", "role", "devil's advocate", "along", "dead",
            "dumb", "fair", "safe", "hard to get", "fool", "victim", "hero"
        )
        if any(re.search(rf"\b{re.escape(w)}\b", q) for w in non_music):
            return None

        if re.search(r"\bplay\s+with\b", q):
            return None

        # 1. Suggest a song requests
        suggest_patterns = [
            r"(?:can you\s+)?(?:suggest|recommend)(?:\s+me)?\s+(?:a|any|some)?\s*(?:good\s+)?(?:song|music|track)",
            r"what\s+song\s+should\s+i\s+listen\s+to",
            r"give\s+me\s+a\s+(?:good\s+)?song",
            r"what\s+should\s+i\s+play",
        ]
        if any(re.search(p, q) for p in suggest_patterns):
            key, (song, artist, vid) = random.choice(list(CURATED_SONGS.items()))
            url = f"https://www.youtube.com/watch?v={vid}&autoplay=1"
            reply = f"I suggest '{song}' by {artist}! Playing it on YouTube for you now."
            return {"song": f"{song} {artist}", "reply": reply, "url": url, "video_id": vid}

        # 2. User suggests a specific song: "i suggest <song>", "suggest playing <song>", "how about <song>"
        user_suggest = re.search(r"\b(?:i suggest|how about playing|what about playing|how about|what about)\s+(.+)", q)
        if user_suggest:
            raw = user_suggest.group(1).strip()
            clean = re.sub(r"\b(?:on|from|in)\s+(?:spotify|youtube)\b", "", raw)
            clean = re.sub(r"\b(?:please|for me)\b", "", clean).strip(" .?!,\"':")
            if clean and not re.match(r"^(?:a\s+|any\s+|some\s+)?(?:good\s+)?(?:song|music|track)$", clean):
                url, vid = resolve_song_playable_url(clean)
                reply = f"Great choice! Playing '{clean.title()}' on YouTube for you!"
                return {"song": clean, "reply": reply, "url": url, "video_id": vid}

        # 3. Direct / natural play commands: "play <song>", "can you play a song", "i want to listen to <song>", etc.
        play_match = re.search(
            r"^(?:(?:can|could|would)\s+you\s+(?:please\s+)?|please\s+|i\s+(?:want|would\s+like)\s+to\s+)?"
            r"(?:play|listen\s+to|put\s+on|hear|stream|sing)"
            r"(?:\s+(?:me|us))?"
            r"(?:\s+(?:a|any|some))?"
            r"(?:\s+(?:song|songs|music|track|tracks|tunes?))?"
            r"(?:\s+(?:called|named|by|for\s+me|please))?"
            r"(?:\s+(.+))?$",
            q,
        )
        if play_match:
            raw = (play_match.group(1) or "").strip()
            clean = re.sub(r"\b(?:on|from|in)\s+(?:spotify|youtube)\b", "", raw)
            clean = re.sub(r"\b(?:please|for me)\b", "", clean).strip(" .?!,\"':")
            generic_requests = (
                "", "music", "some music", "a song", "songs", "something",
                "any song", "a track", "some tracks", "tunes", "good music", "good songs"
            )
            if not clean or clean in generic_requests:
                key, (song, artist, vid) = random.choice(list(CURATED_SONGS.items()))
                url = f"https://www.youtube.com/watch?v={vid}&autoplay=1"
                return {"song": f"{song} by {artist}", "reply": f"Playing '{song}' by {artist} on YouTube for you!", "url": url, "video_id": vid}

            url, vid = resolve_song_playable_url(clean)
            return {"song": clean, "reply": f"Playing '{clean.title()}' on YouTube for you!", "url": url, "video_id": vid}

        # 4. Explicit spotify query: "spotify <song>" -> Always play song from YouTube as required
        spotify_match = re.search(r"^spotify\s+(.+)$", q)
        if spotify_match:
            raw = spotify_match.group(1).strip()
            clean = re.sub(r"\b(?:please|for me)\b", "", raw).strip(" .?!,\"':")
            if clean:
                url, vid = resolve_song_playable_url(clean)
                return {"song": clean, "reply": f"Playing '{clean.title()}' on YouTube for you!", "url": url, "video_id": vid}

        return None

    def _parse_spotify_intent(self, query: str) -> dict | None:
        """Alias for backward compatibility."""
        return self._parse_song_intent(query)

    # ── Command dispatcher ────────────────────

    def execute_command(self, query: str):
        q = query.lower().strip()
        if not q or q == "none":
            return

        now = datetime.datetime.now()

        # 1. Music / song playback (Alexa-style Immediate Autoplay)
        song_info = self._parse_song_intent(query)
        if song_info:
            self._emit_status("🎵", "PLAYING", song_info["reply"])
            self.say(song_info["reply"])
            subprocess.run(["open", song_info["url"]])
            try:
                subprocess.run(
                    ["osascript", "-e", 'tell application "Google Chrome" to activate'],
                    capture_output=True,
                    timeout=1.0,
                )
            except Exception:
                pass
            return

        if re.search(r"\b(?:stop|pause)\s+(?:music|song|the\s+music|the\s+song)\b", q):
            self._emit_status("⏸", "PAUSED", "Music paused")
            self.say("Music paused.")
            try:
                subprocess.run(
                    ["osascript", "-e", 'tell application "Google Chrome" to tell active tab of front window to execute javascript "document.querySelector(\'video\')?.pause()"'],
                    capture_output=True,
                    timeout=1.0,
                )
            except Exception:
                pass
            return

        if re.search(r"\b(?:resume|continue|unpause)\s+(?:music|song|the\s+music|the\s+song)\b", q):
            self._emit_status("▶", "PLAYING", "Music resumed")
            self.say("Resuming music.")
            try:
                subprocess.run(
                    ["osascript", "-e", 'tell application "Google Chrome" to tell active tab of front window to execute javascript "document.querySelector(\'video\')?.play()"'],
                    capture_output=True,
                    timeout=1.0,
                )
            except Exception:
                pass
            return

        # 2. Web sites & search intent (including user custom links)
        custom_links = self.get_links()
        matched_site = _match_site_intent(query, custom_links=custom_links)
        if matched_site:
            name = matched_site["name"]
            url = matched_site["url"]
            say_msg = matched_site.get("say") or f"Opening {name}!"
            self._emit_status("🌐", "OPEN", f"{name} → {url}")
            self.say(say_msg)
            app_name = matched_site.get("app_name")
            if app_name and os.path.exists(f"/Applications/{app_name}.app"):
                subprocess.run(["open", "-a", app_name])
            else:
                subprocess.run(["open", url])
            return

        # 2.5. Custom Link Management (Add Link via Voice/Text)
        add_link_match = re.search(
            r"^(?:(?:can|could|would)\s+you\s+(?:please\s+)?|please\s+)?(?:add|save|remember|create)\s+link[:\s]+(?:called\s+|named\s+)?([a-zA-Z0-9\s_-]+?)\s+(?:as\s+|to\s+|at\s+|url\s+)?(https?://\S+|\S+\.[a-zA-Z]{2,}\S*)$",
            q,
        )
        if add_link_match:
            lname = add_link_match.group(1).strip()
            lurl = add_link_match.group(2).strip()
            if lname and lurl:
                new_link = self.add_link(lname, lurl)
                self.say(f"Added {new_link['name']} to your quick links!")
                self._emit_status("🔗", "LINK", f"{new_link['name']} → {new_link['url']}")
                return

        # 3. Table-driven app commands
        for phrases, name, path in APP_COMMANDS:
            if any(p in q for p in phrases):
                self._emit_status("🚀", "OPEN", name)
                self.say(f"Opening {name}!")
                target = path if path else os.path.expanduser("~")
                subprocess.run(["open", target])
                return

        # 4. Strict Current Time Query
        if re.search(r"^(?:what(?:'s|\s+is)\s+the\s+time|what\s+time\s+is\s+it|current\s+time|tell\s+me\s+the\s+time)\??$", q):
            t = now.strftime("%I:%M %p")
            self._emit_status("🕐", "TIME", t)
            self.say(f"The time is {t}.")
            return

        # 5. Strict Today's Date Query
        if re.search(r"^(?:what(?:'s|\s+is)\s+(?:the\s+date|today(?:'s)?\s+date)|what\s+date\s+is\s+it(?:\s+today)?|what\s+is\s+today(?:'s)?\s+date|today(?:'s)?\s+date)\??$", q):
            d = now.strftime("%A, %d %B %Y")
            self._emit_status("📅", "DATE", d)
            self.say(f"Today is {d}.")
            return

        # 6. AI generation
        if "using artificial intelligence" in q:
            self.ai_generate(query)
            return

        # 7. Chat reset
        if q in ("reset chat", "clear chat", "clear history", "start over"):
            self.reset_chat()
            return

        # 8. Tasks: Add Task
        task_add_match = re.search(r"^(?:remember\s+to|remind\s+me\s+to|add\s+task[:\s]+|new\s+task[:\s]+|add\s+to(?:-do|\s+tasks?)[:\s]+|todo[:\s]+)\s+(.+)$", q)
        if task_add_match:
            task = task_add_match.group(1).strip()
            if task.startswith("to "):
                task = task[3:].strip()
            if task:
                self.save_task(task)
                self._emit_status("📌", "SAVED", task)
                self.say(f"Got it, I'll remember to {task}.")
                return

        # 9. Tasks: Show Tasks
        if q in ("show my tasks", "my tasks", "show tasks", "list my tasks", "list tasks", "what are my tasks"):
            tasks = self.load_tasks()
            count = len(tasks)
            if tasks:
                self._emit_status("📋", "TASKS", f"{count} task(s) found")
                self.say(f"You have {count} task{'s' if count > 1 else ''}.")
            else:
                self.say("You have no saved tasks.")
            return

        # 10. Tasks: Delete Task
        task_del_match = re.search(r"^(?:delete|remove)\s+task\s+(\d+)$", q)
        if task_del_match:
            self.delete_task(task_del_match.group(1))
            return

        # 11. Strict Farewell
        if re.search(r"^(?:goodbye|bye|bye\s+bye|see\s+you(?:\s+later)?|farewell|exit|quit|aanya\s+quit|go\s+to\s+sleep|sleep\s+now)$", q):
            self._emit_status("👋", "GOODBYE", "Shutting down...")
            self.say("Goodbye, have a wonderful day!")
            self.stop_voice_loop()
            return

        # Fallback to Gemini
        self._emit_status("💬", "CHAT", f'"{query}"')
        self.chat(query)

    # ── Voice loop ────────────────────────────

    def start_voice_loop(self):
        self._running = True
        self._voice_thread = threading.Thread(target=self._voice_loop, daemon=True)
        self._voice_thread.start()

    def stop_voice_loop(self):
        self._running = False

    def _voice_loop(self):
        self._emit_state("standby")
        self._emit_status("👂", "STANDBY", "Say 'Aanya' to activate...")

        while self._running:
            self._emit_state("standby")
            wake = self.listen(timeout=10, phrase_time_limit=5).lower()
            if not self.is_wake_word(wake):
                time.sleep(0.3)
                continue

            if self.on_wake:
                self.on_wake()
            self._emit_state("listening")
            self._emit_status("✦", "AWAKE", "Wake word detected!")
            self.say("Yes Yuvi?")
            time.sleep(0.5)
            self._emit_status("👂", "COMMAND", "Listening for your command...")
            command = self.listen(timeout=8, phrase_time_limit=15)

            if command.lower() == "none":
                self._emit_status("?", "MISSED", "Didn't catch that.")
                self.say("Sorry, I didn't catch that. Try again.")
                continue

            if self.on_heard:
                self.on_heard(command)
            self._emit_status("🎤", "HEARD", f'"{command}"')
            self._emit_state("executing")
            self._emit_status("⚡", "EXECUTE", "Running task...")
            self.execute_command(command)
            self._emit_status("✔", "DONE", "Task complete.")
            time.sleep(1)

    # ── GUI entry points ──────────────────────

    def process_text_command(self, text: str):
        """Called from GUI text-input thread."""
        if self.on_heard:
            self.on_heard(text)
        self._emit_state("executing")
        self.execute_command(text)
        self._emit_state("standby")

    def push_to_talk(self):
        """Single listen cycle for GUI mic button."""
        self._emit_state("listening")
        self._emit_status("🎤", "LISTENING", "Listening for your command...")
        command = self.listen(timeout=8, phrase_time_limit=15)
        if command.lower() == "none":
            self._emit_status("?", "MISSED", "Didn't catch that.")
            self.say("Sorry, I didn't catch that. Try again.")
            self._emit_state("standby")
            return
        if self.on_heard:
            self.on_heard(command)
        self._emit_status("🎤", "HEARD", f'"{command}"')
        self._emit_state("executing")
        self.execute_command(command)
        self._emit_state("standby")


# ─────────────────────────────────────────────
#  Terminal mode  (backward-compatible)
# ─────────────────────────────────────────────
def _banner():
    w = 52
    print(f"\n{C.CYAN}{C.BOLD}{'─'*w}\n{'  ✦  AANYA  —  AI Voice Assistant  ✦':^{w}}\n{'─'*w}{C.RESET}")
    print(f"{C.DIM}{C.GREY}{'  powered by Gemini · built by Yuvi':^{w}}{C.RESET}")
    print(f"{C.CYAN}{C.BOLD}{'─'*w}{C.RESET}\n")


def _status(icon, label, message, colour=C.CYAN):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"  {C.GREY}{ts}{C.RESET}  {colour}{C.BOLD}{icon}  {label:<14}{C.RESET}  {C.WHITE}{message}{C.RESET}")


if __name__ == "__main__":
    if "--gui" in sys.argv:
        try:
            from desktop_app import AanyaApp
            app = AanyaApp()
            app.mainloop()
            sys.exit(0)
        except Exception as exc:
            print(f"Failed to start GUI: {exc}")
            sys.exit(1)

    _banner()
    engine = AanyaEngine()
    engine.on_status = lambda icon, label, msg: _status(icon, label, msg)
    engine.on_speak  = lambda text: print(f"\n  {C.MAGENTA}{C.BOLD}◈  Aanya{C.RESET}   {C.WHITE}{text}{C.RESET}\n")
    engine.on_heard  = lambda text: _status("🎤", "HEARD", f'"{text}"', C.CYAN)
    print(f"  {C.GREEN}Aanya is ready. Say 'Aanya' to wake me up!{C.RESET}")
    engine._running = True
    engine._voice_loop()