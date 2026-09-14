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
}

# Rich site rules supporting multiple voice and text aliases
SITE_RULES = [
    {
        "name": "GitHub",
        "aliases": ["github", "git hub", "git-hub", "gethub"],
        "url": "https://github.com/Yuvika108",
    },
    {
        "name": "WhatsApp",
        "aliases": ["whatsapp", "whats app", "what's app", "what app", "whatsapp web", "whats app web"],
        "url": "https://web.whatsapp.com/",
        "app_name": "WhatsApp",
    },
    {
        "name": "YouTube",
        "aliases": ["youtube", "you tube"],
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
        "aliases": ["spotify"],
        "url": "https://open.spotify.com",
    },
    {
        "name": "LeetCode",
        "aliases": ["leetcode", "leet code"],
        "url": "https://leetcode.com/u/Yuv1ka/",
    },
]

# Table-driven app commands: (trigger_phrases, say_name, open_path)
APP_COMMANDS = [
    (["open chrome"],                               "Chrome",   "/Applications/Google Chrome.app"),
    (["open brave"],                                "Brave",    "/Applications/Brave Browser.app"),
    (["open finder", "open files"],                 "Finder",   None),          # None → home dir
    (["open music", "play music"],                  "Spotify",  "https://open.spotify.com/"),
    (["open whatsapp", "open whats app", "open what's app", "open whatsapp web"], "WhatsApp", "https://web.whatsapp.com/"),
    (["open github", "open git hub", "open git-hub"], "GitHub",   "https://github.com/Yuv1ka/"),
]

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

WAKE_VARIANTS = {"aanya", "anya", "hanya", "tanya", "anna", "ana", "onia", "nia"}
DATA_DIR = os.path.expanduser("~/.aanya")
os.makedirs(DATA_DIR, exist_ok=True)
TASK_FILE = os.path.join(DATA_DIR, "tasks.txt")


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
        self.system_instruction = (
            "You are Aanya, a helpful, smart, and concise AI assistant made by Yuvi. "
            "Your responses are spoken aloud, so keep them natural and brief."
        )
        self.client = None
        self.chat_session = None
        if gemini_key:
            try:
                self.client = genai.Client(api_key=gemini_key)
                self.chat_session = self.client.chats.create(
                    model=DEFAULT_MODEL,
                    config=types.GenerateContentConfig(
                        system_instruction=self.system_instruction
                    )
                )
            except Exception as e:
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
        if not self.chat_session:
            self._emit_status("✗", "NO KEY", "Set gemini_key in config.py")
            self.say("Please configure your Gemini API key in config.py to chat.")
            return ""
        self._emit_state("thinking")
        self._emit_status("💬", "THINKING", "Contacting Gemini...")
        try:
            response = self.chat_session.send_message(query)
            reply = response.text
            # Keep history bounded if possible (genai stores it in get_history())
            history = self.chat_session.get_history()
            if len(history) > 10:
                # We reset and seed the last 10 messages if it gets too long
                recent = history[-10:]
                self.chat_session = self.client.chats.create(
                    model=DEFAULT_MODEL,
                    history=recent,
                    config=types.GenerateContentConfig(system_instruction=self.system_instruction)
                )
            self.say(reply)
            return reply
        except Exception as e:
            self._emit_status("✗", "ERROR", str(e))
            self.say("I'm having trouble connecting to my brain right now.")
            return ""

    def ai_generate(self, prompt: str):
        if not self.client:
            self._emit_status("✗", "NO KEY", "Set gemini_key in config.py")
            self.say("Please configure your Gemini API key in config.py.")
            return
        self.say("Generating response, please wait...")
        self._emit_state("thinking")
        self._emit_status("⚙", "AI MODE", "Generating content...")
        try:
            response = self.client.models.generate_content(
                model=DEFAULT_MODEL,
                contents=prompt
            )
            reply = response.text
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
            self.say("I encountered an error while generating the response.")

    def reset_chat(self):
        if not self.client:
            self._emit_status("✗", "NO KEY", "Set gemini_key in config.py")
            return
        self.chat_session = self.client.chats.create(
            model=DEFAULT_MODEL,
            config=types.GenerateContentConfig(system_instruction=self.system_instruction)
        )
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

    # ── Wake word ─────────────────────────────

    @staticmethod
    def is_wake_word(text: str) -> bool:
        return any(w in WAKE_VARIANTS for w in text.lower().split())

    # ── Spotify / Song Playback (Alexa-style) ─────────────────────────────────

    def _parse_spotify_intent(self, query: str) -> dict | None:
        """Parse Alexa-style Spotify song playback and recommendation requests."""
        q = query.lower().strip()

        # Exclude non-music actions that use the word 'play'
        non_music = ("youtube", "video", "chess", "cricket", "game", "football", "tennis")
        if any(w in q for w in non_music):
            return None

        # 1. Suggest a song requests
        suggest_patterns = [
            r"(?:can you\s+)?(?:suggest|recommend)(?:\s+me)?\s+(?:a|any|some)?\s*(?:good\s+)?(?:song|music|track)",
            r"what\s+song\s+should\s+i\s+listen\s+to",
            r"give\s+me\s+a\s+(?:good\s+)?song",
            r"what\s+should\s+i\s+play",
        ]
        if any(re.search(p, q) for p in suggest_patterns):
            curated_suggestions = [
                ("Bohemian Rhapsody", "Queen"),
                ("Blinding Lights", "The Weeknd"),
                ("Shape of You", "Ed Sheeran"),
                ("Starboy", "The Weeknd"),
                ("Flowers", "Miley Cyrus"),
                ("As It Was", "Harry Styles"),
                ("Believer", "Imagine Dragons"),
                ("Levitating", "Dua Lipa"),
                ("Viva La Vida", "Coldplay"),
                ("Stay", "Justin Bieber"),
                ("Kesariya", "Arijit Singh"),
            ]
            song, artist = random.choice(curated_suggestions)
            target = f"{song} {artist}"
            url = f"https://open.spotify.com/search/{urllib.parse.quote(target)}"
            reply = f"I suggest '{song}' by {artist}! Playing it on Spotify."
            return {"song": target, "reply": reply, "url": url}

        # 2. User suggests a specific song: "i suggest <song>", "suggest playing <song>", "how about <song>"
        user_suggest = re.search(r"\b(?:i suggest|how about playing|what about playing|how about|what about)\s+(.+)", q)
        if user_suggest:
            raw = user_suggest.group(1).strip()
            clean = re.sub(r"\b(?:on|from|in)\s+spotify\b", "", raw)
            clean = re.sub(r"\b(?:please|for me)\b", "", clean).strip(" .?!,\"':")
            if clean and not re.match(r"^(?:a\s+|any\s+|some\s+)?(?:good\s+)?(?:song|music|track)$", clean):
                url = f"https://open.spotify.com/search/{urllib.parse.quote(clean)}"
                return {"song": clean, "reply": f"Great choice! Playing {clean.title()} on Spotify!", "url": url}

        # 3. Direct play commands: "play <song>", "listen to <song>", "put on <song>"
        play_match = re.search(r"\b(?:play|listen to|put on)\s+(.+)", q)
        if play_match:
            raw = play_match.group(1).strip()
            clean = re.sub(r"\b(?:on|from|in)\s+spotify\b", "", raw)
            clean = re.sub(r"\b(?:please|for me)\b", "", clean).strip(" .?!,\"':")
            if not clean or clean in ("music", "some music", "a song", "songs", "spotify", "something"):
                return {"song": "music", "reply": "Playing music on Spotify!", "url": "https://open.spotify.com"}
            url = f"https://open.spotify.com/search/{urllib.parse.quote(clean)}"
            return {"song": clean, "reply": f"Playing {clean.title()} on Spotify!", "url": url}

        # 4. Explicit spotify query: "spotify <song>"
        spotify_match = re.search(r"\bspotify\s+(.+)", q)
        if spotify_match:
            raw = spotify_match.group(1).strip()
            clean = re.sub(r"\b(?:please|for me)\b", "", raw).strip(" .?!,\"':")
            if clean:
                url = f"https://open.spotify.com/search/{urllib.parse.quote(clean)}"
                return {"song": clean, "reply": f"Playing {clean.title()} on Spotify!", "url": url}

        return None

    # ── Command dispatcher ────────────────────

    def execute_command(self, query: str):
        q = query.lower().strip()
        if q == "none":
            return

        # Spotify / song playback (Alexa-style)
        spotify_info = self._parse_spotify_intent(query)
        if spotify_info:
            self._emit_status("🎵", "SPOTIFY", spotify_info["reply"])
            self.say(spotify_info["reply"])
            subprocess.run(["open", spotify_info["url"]])
            return

        # Web sites & rich aliases
        matched_site = None
        if not any(q.startswith(w) for w in ("what is ", "who is ", "how to ", "why is ", "tell me about ")):
            for rule in SITE_RULES:
                if any(alias in q for alias in rule["aliases"]):
                    matched_site = rule
                    break

        if matched_site:
            name = matched_site["name"]
            url = matched_site["url"]
            self._emit_status("🌐", "OPEN", f"{name} → {url}")
            self.say(f"Opening {name}!")
            app_name = matched_site.get("app_name")
            if app_name and os.path.exists(f"/Applications/{app_name}.app"):
                subprocess.run(["open", "-a", app_name])
            else:
                subprocess.run(["open", url])
            return

        # Table-driven app commands
        for phrases, name, path in APP_COMMANDS:
            if any(p in q for p in phrases):
                self._emit_status("🚀", "OPEN", name)
                self.say(f"Opening {name}!")
                target = path if path else os.path.expanduser("~")
                subprocess.run(["open", target])
                return

        # Time & date
        now = datetime.datetime.now()
        if "time" in q:
            t = now.strftime("%I:%M %p")
            self._emit_status("🕐", "TIME", t)
            self.say(f"The time is {t}.")
            return
        if "date" in q or "today" in q:
            d = now.strftime("%A, %d %B %Y")
            self._emit_status("📅", "DATE", d)
            self.say(f"Today is {d}.")
            return

        # AI generation
        if "using artificial intelligence" in q:
            self.ai_generate(query)
            return

        # Chat reset
        if "reset chat" in q:
            self.reset_chat()
            return

        # Tasks
        if "remember" in q:
            task = q.replace("remember", "").strip()
            self.save_task(task)
            self._emit_status("📌", "SAVED", task)
            self.say(f"Got it, I'll remember: {task}.")
            return

        if "show my tasks" in q or "my tasks" in q:
            tasks = self.load_tasks()
            count = len(tasks)
            if tasks:
                self._emit_status("📋", "TASKS", f"{count} task(s) found")
                self.say(f"You have {count} task{'s' if count > 1 else ''}.")
            else:
                self.say("You have no saved tasks.")
            return

        if "delete task" in q:
            self.delete_task(q.replace("delete task", "").strip())
            return

        # Exit
        if any(w in q for w in ("aanya quit", "goodbye", "bye", "sleep", "exit")):
            self._emit_status("👋", "GOODBYE", "Shutting down...")
            self.say("Goodbye Yuvi, have a great day!")
            self.stop_voice_loop()
            return

        # Fallback
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
    _banner()
    engine = AanyaEngine()
    engine.on_status = lambda icon, label, msg: _status(icon, label, msg)
    engine.on_speak  = lambda text: print(f"\n  {C.MAGENTA}{C.BOLD}◈  Aanya{C.RESET}   {C.WHITE}{text}{C.RESET}\n")
    engine.on_heard  = lambda text: _status("🎤", "HEARD", f'"{text}"', C.CYAN)
    print(f"  {C.GREEN}Aanya is ready. Say 'Aanya' to wake me up!{C.RESET}")
    engine._running = True
    engine._voice_loop()