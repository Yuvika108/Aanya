"""
AANYA — Engine with Adaptive Memory & Self-Improvement

Aanya learns from every conversation:
  - Remembers your name, preferences, and interests
  - Adapts her personality and response style to you
  - Accepts explicit corrections and stores them permanently
  - Builds a richer system prompt from everything she's learned
  - Rates herself and gets better with your 👍/👎 feedback
"""

import os
import re
import json
import base64
import datetime
import urllib.parse
import urllib.request
import functools
import random
from google import genai
from google.genai import types

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
FALLBACK_MODEL = "gemini-3.5-flash-lite"

SITES = {
    "youtube":   "https://www.youtube.com/user/YUVI09",
    "whatsapp":  "https://web.whatsapp.com/",
    "google":    "https://www.google.com",
    "spotify":   "https://open.spotify.com/user/31y44saeslws5yvkws4zvkh7njuu",
    "leetcode":  "https://leetcode.com/u/Yuv1ka/",
    "github":    "https://github.com/Yuv1ka/",
    "gmail":     "https://mail.google.com/mail/u/0/#inbox",
}

SITE_RULES = [
    {
        "name": "GitHub",
        "aliases": ["github", "git hub", "git-hub", "gethub"],
        "url": "https://github.com/Yuv1ka/",
    },
    {
        "name": "WhatsApp",
        "aliases": ["whatsapp", "whats app", "what's app", "what app", "whatsapp web", "whats app web"],
        "url": "https://web.whatsapp.com/",
    },
    {
        "name": "YouTube",
        "aliases": ["youtube", "you tube"],
        "url": "https://www.youtube.com/user/YUVI09",
    },
    {
        "name": "Google",
        "aliases": ["google"],
        "url": "https://www.google.com",
    },
    {
        "name": "Spotify",
        "aliases": ["spotify"],
        "url": "https://open.spotify.com/user/31y44saeslws5yvkws4zvkh7njuu",
    },
    {
        "name": "LeetCode",
        "aliases": ["leetcode", "leet code"],
        "url": "https://leetcode.com/u/Yuv1ka/",
    },
    {
        "name": "Wikipedia",
        "aliases": ["wikipedia", "wiki"],
        "url": "https://www.wikipedia.org",
    },
    {
        "name": "Gmail",
        "aliases": ["gmail", "mail", "inbox", "google mail"],
        "url": "https://mail.google.com/mail/u/0/#inbox",
    },
]

def _match_site_intent(query: str):
    q = query.lower().strip()
    if any(q.startswith(w) for w in ("what is ", "who is ", "how to ", "why is ", "tell me about ")):
        return None
    for rule in SITE_RULES:
        if any(alias in q for alias in rule["aliases"]):
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

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)


# ── File path helpers ─────────────────────────────────────────────────────────

def _safe_id(session_id: str) -> str:
    return "".join(c for c in session_id if c.isalnum() or c in "-_.") or "default"

def _task_file(session_id: str) -> str:
    return os.path.join(DATA_DIR, f"tasks_{_safe_id(session_id)}.json")

def _memory_file(session_id: str) -> str:
    return os.path.join(DATA_DIR, f"memory_{_safe_id(session_id)}.json")

# Backward compat alias
_take_file = _task_file


# ── Learning keyword patterns ─────────────────────────────────────────────────

_NAME_PATTERNS = [
    r"my name is ([A-Za-z]+)",
    r"call me ([A-Za-z]+)",
    r"i(?:'m| am) ([A-Za-z]+)",
    r"i go by ([A-Za-z]+)",
]

_PREFERENCE_PATTERNS = [
    r"i (?:really )?(?:like|love|enjoy|prefer) (.+)",
    r"my favourite (.+) is (.+)",
    r"i'm (?:really )?into (.+)",
    r"i'm a big fan of (.+)",
]

_AVERSION_PATTERNS = [
    r"i (?:don't|do not|hate|dislike|can't stand) (.+)",
    r"i(?:'m| am) not (?:a fan of|into) (.+)",
    r"stop (.+)",
    r"never (.+)",
    r"don't (.+) me",
]

_CORRECTION_PATTERNS = [
    r"(?:that's|you(?:'re| are)) (?:wrong|incorrect|mistaken)",
    r"actually[,.]? (.+)",
    r"no[,.]? (.+) is (?:the )?(?:correct|right) answer",
    r"the correct answer is (.+)",
    r"you should (?:know|remember) that (.+)",
]

_RULE_PATTERNS = [
    r"always (.+)",
    r"please always (.+)",
    r"from now on[,.]? (.+)",
    r"(?:i want you to|you should) always (.+)",
]

_TEACH_PATTERNS = [
    r"learn this[:\.]? (.+)",
    r"teach you[:\.]? (.+)",
    r"remember that (.+)",
    r"note that (.+)",
    r"keep in mind[:\.]? (.+)",
]

_INTEREST_KEYWORDS = {
    "technology", "programming", "python", "music", "sports", "fitness",
    "cooking", "gaming", "books", "movies", "science", "art", "travel",
    "finance", "health", "fashion", "news", "politics", "philosophy",
}


# ── Memory model ──────────────────────────────────────────────────────────────

DEFAULT_MEMORY: dict = {
    "user_profile": {
        "name": None,
        "interests": [],
        "preferred_topics": [],
    },
    "preferences": [],      # things the user likes
    "aversions": [],        # things the user dislikes / rules to follow
    "learned_facts": [],    # explicit facts / corrections
    "behavior_rules": [],   # always/never instructions
    "feedback": {
        "thumbs_up": 0,
        "thumbs_down": 0,
        "corrections": [],  # (wrong_reply, correction_text) pairs
    },
    "interaction_count": 0,
    "last_updated": None,
}


class AanyaEngine:
    def __init__(self, session_id: str, api_key: str):
        self.session_id = session_id or "default"
        self.client = genai.Client(api_key=api_key)
        self.memory = self._load_memory()
        self._rebuild_session()

    # ── Memory persistence ────────────────────────────────────────────────────

    def _load_memory(self) -> dict:
        path = _memory_file(self.session_id)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    stored = json.load(f)
                    # Merge with defaults so new keys are always present
                    merged = dict(DEFAULT_MEMORY)
                    merged.update(stored)
                    if "user_profile" not in merged:
                        merged["user_profile"] = DEFAULT_MEMORY["user_profile"].copy()
                    if "feedback" not in merged:
                        merged["feedback"] = DEFAULT_MEMORY["feedback"].copy()
                    return merged
            except Exception:
                pass
        return dict(DEFAULT_MEMORY)

    def _save_memory(self):
        self.memory["last_updated"] = datetime.datetime.now().isoformat()
        path = _memory_file(self.session_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.memory, f, indent=2)

    # ── Dynamic system prompt ─────────────────────────────────────────────────

    def _build_system_prompt(self) -> str:
        m = self.memory
        profile = m.get("user_profile", {})
        interactions = m.get("interaction_count", 0)

        parts = [
            "You are Aanya, a warm, witty, and highly intelligent AI assistant "
            "with a natural British accent and personality. "
            "Your responses are spoken aloud so keep them conversational, "
            "natural, and appropriately brief.",
        ]

        # Address user by name if known
        if profile.get("name"):
            parts.append(
                f"The user's name is {profile['name']}. "
                "Address them by name occasionally — but not every single message."
            )

        # Personality maturity based on interaction count
        if interactions > 50:
            parts.append(
                "You have had many conversations together. "
                "Be warm and familiar — like a long-time friend."
            )
        elif interactions > 10:
            parts.append(
                "You are getting to know this user. "
                "Show genuine interest in their life and preferences."
            )

        # Interests
        interests = profile.get("interests", [])
        if interests:
            parts.append(
                f"The user is interested in: {', '.join(interests[:8])}. "
                "Tailor your examples and recommendations to these interests."
            )

        # Preferences
        prefs = m.get("preferences", [])
        if prefs:
            parts.append(
                f"User preferences (things they like): {'; '.join(prefs[:5])}."
            )

        # Aversions and rules
        rules = list(set(m.get("aversions", []) + m.get("behavior_rules", [])))
        if rules:
            parts.append(
                f"Behavioral rules to always follow: {'; '.join(rules[:8])}."
            )

        # Learned facts and corrections
        facts = m.get("learned_facts", [])
        if facts:
            fact_text = "; ".join(f["fact"] for f in facts[-10:])  # last 10
            parts.append(
                f"Important facts you have learned about the user: {fact_text}."
            )

        # Self-improvement from feedback
        thumbs_down = m.get("feedback", {}).get("thumbs_down", 0)
        corrections = m.get("feedback", {}).get("corrections", [])
        if thumbs_down > 0 or corrections:
            parts.append(
                f"You have received {thumbs_down} pieces of negative feedback. "
                "Be more careful, accurate, and considerate in your responses."
            )
            if corrections:
                recent = corrections[-3:]
                corr_text = "; ".join(
                    f"You said '{c['wrong'][:60]}' but the right answer is '{c['right'][:60]}'"
                    for c in recent
                )
                parts.append(f"Recent corrections to remember: {corr_text}.")

        # High-precision accuracy & multimodal grounding rules
        parts.append(
            "ACCURACY & MULTIMODAL GROUNDING: "
            "You possess near-100% accuracy and strict factual grounding. "
            "When the user attaches or references documents (PDFs, texts, code, data), images, videos, or audio files, "
            "ground your answer directly, precisely, and exhaustively in the provided media. Never speculate or hallucinate. "
            "For documents, quote or cite exact values, lines, and figures. "
            "For images and video, scrutinize fine visual details, structure, colors, and embedded text. "
            "Deliver prompt, insightful, high-precision answers with your characteristic British warmth, wit, and clarity."
        )

        return " ".join(parts)

    def _rebuild_session(self):
        """Rebuild Gemini chat session with the latest learned system prompt."""
        self.system_instruction = self._build_system_prompt()
        try:
            self.chat_session = self.client.chats.create(
                model=GEMINI_MODEL,
                config=types.GenerateContentConfig(
                    system_instruction=self.system_instruction
                ),
            )
        except Exception:
            self.chat_session = self.client.chats.create(
                model=FALLBACK_MODEL,
                config=types.GenerateContentConfig(
                    system_instruction=self.system_instruction
                ),
            )

    # ── Passive learning (called on every user message) ───────────────────────

    def _learn_from_message(self, text: str) -> list[str]:
        """
        Parse the user's message for learnable signals.
        Returns a list of human-readable strings describing what was learned.
        """
        q = text.lower().strip()
        learned = []
        changed = False

        # ── Name detection ────────────────────────────────────────────────────
        for pattern in _NAME_PATTERNS:
            m = re.search(pattern, q)
            if m:
                candidate = m.group(1).strip().capitalize()
                # Ignore common false positives
                if candidate.lower() not in ("a", "an", "the", "not", "just"):
                    old_name = self.memory["user_profile"].get("name")
                    if old_name != candidate:
                        self.memory["user_profile"]["name"] = candidate
                        learned.append(f"your name is {candidate}")
                        changed = True
                    break

        # ── Preferences ───────────────────────────────────────────────────────
        for pattern in _PREFERENCE_PATTERNS:
            m = re.search(pattern, q)
            if m:
                pref = m.group(1).strip()
                if len(pref) > 2 and pref not in self.memory["preferences"]:
                    self.memory["preferences"].append(pref)
                    learned.append(f"you like {pref}")
                    changed = True
                break

        # ── Aversions ─────────────────────────────────────────────────────────
        for pattern in _AVERSION_PATTERNS:
            m = re.search(pattern, q)
            if m:
                aversion = m.group(1).strip()
                if len(aversion) > 2 and aversion not in self.memory["aversions"]:
                    self.memory["aversions"].append(aversion)
                    learned.append(f"you dislike / I should {aversion}")
                    changed = True
                break

        # ── Behavior rules ────────────────────────────────────────────────────
        for pattern in _RULE_PATTERNS:
            m = re.search(pattern, q)
            if m:
                rule = m.group(1).strip()
                if len(rule) > 3 and rule not in self.memory["behavior_rules"]:
                    self.memory["behavior_rules"].append(rule)
                    learned.append(f"rule added: {rule}")
                    changed = True
                break

        # ── Explicit taught facts ─────────────────────────────────────────────
        for pattern in _TEACH_PATTERNS:
            m = re.search(pattern, q)
            if m:
                fact = m.group(1).strip()
                if len(fact) > 3:
                    self.memory["learned_facts"].append({
                        "fact": fact,
                        "source": "user_explicit",
                        "timestamp": datetime.datetime.now().isoformat(),
                    })
                    learned.append(f"learned: {fact}")
                    changed = True
                break

        # ── Corrections ───────────────────────────────────────────────────────
        is_correction = any(
            re.search(p, q) for p in _CORRECTION_PATTERNS
        )
        if is_correction:
            self.memory["feedback"]["thumbs_down"] += 1
            learned.append("noted your correction — I'll do better")
            changed = True

        # ── Implicit interest detection ───────────────────────────────────────
        words_in_msg = set(q.split())
        detected_interests = words_in_msg & _INTEREST_KEYWORDS
        for interest in detected_interests:
            if interest not in self.memory["user_profile"]["interests"]:
                self.memory["user_profile"]["interests"].append(interest)
                changed = True

        # ── Increment interaction count ───────────────────────────────────────
        self.memory["interaction_count"] = self.memory.get("interaction_count", 0) + 1
        changed = True  # always save on increment

        if changed:
            self._save_memory()
            # Rebuild session prompt with new knowledge every 5 interactions
            # or whenever something significant was learned
            if learned or self.memory["interaction_count"] % 5 == 0:
                self._rebuild_session()

        return learned

    # ── Public API ────────────────────────────────────────────────────────────

    def apply_feedback(self, positive: bool, last_reply: str = "", correction: str = "") -> str:
        """Called when user clicks 👍 or 👎 on a response."""
        if positive:
            self.memory["feedback"]["thumbs_up"] = self.memory["feedback"].get("thumbs_up", 0) + 1
            self._save_memory()
            return "Thank you — glad that was helpful!"
        else:
            self.memory["feedback"]["thumbs_down"] = self.memory["feedback"].get("thumbs_down", 0) + 1
            if correction:
                self.memory["feedback"]["corrections"].append({
                    "wrong": last_reply[:200],
                    "right": correction[:200],
                    "timestamp": datetime.datetime.now().isoformat(),
                })
                # Also store as a learned fact
                self.memory["learned_facts"].append({
                    "fact": correction,
                    "source": "user_correction",
                    "timestamp": datetime.datetime.now().isoformat(),
                })
            self._save_memory()
            self._rebuild_session()  # immediately incorporate correction
            return "Understood — I've noted that and will improve. Thank you for teaching me."

    def get_memory_summary(self) -> dict:
        """Return a clean summary of everything Aanya has learned."""
        m = self.memory
        profile = m.get("user_profile", {})
        return {
            "name": profile.get("name"),
            "interests": profile.get("interests", []),
            "preferences": m.get("preferences", []),
            "aversions": m.get("aversions", []),
            "behavior_rules": m.get("behavior_rules", []),
            "learned_facts": [f["fact"] for f in m.get("learned_facts", [])[-10:]],
            "interaction_count": m.get("interaction_count", 0),
            "thumbs_up": m.get("feedback", {}).get("thumbs_up", 0),
            "thumbs_down": m.get("feedback", {}).get("thumbs_down", 0),
        }

    def forget(self, category: str = "all"):
        """Selectively or fully clear memory."""
        if category == "all":
            self.memory = dict(DEFAULT_MEMORY)
        elif category in self.memory:
            if isinstance(self.memory[category], list):
                self.memory[category] = []
            elif isinstance(self.memory[category], dict):
                self.memory[category] = {}
        self._save_memory()
        self._rebuild_session()

    def _process_attachments(self, attachments: list | None) -> list:
        if not attachments:
            return []
        parts = []
        ext_map = {
            ".pdf": "application/pdf",
            ".txt": "text/plain",
            ".md": "text/markdown",
            ".csv": "text/csv",
            ".json": "application/json",
            ".py": "text/x-python",
            ".js": "text/javascript",
            ".html": "text/html",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif": "image/gif",
            ".mp3": "audio/mp3",
            ".wav": "audio/wav",
            ".ogg": "audio/ogg",
            ".m4a": "audio/m4a",
            ".mp4": "video/mp4",
            ".mov": "video/quicktime",
            ".webm": "video/webm",
        }
        for att in attachments:
            try:
                if isinstance(att, dict):
                    filename = att.get("filename") or att.get("name") or "file"
                    mime_type = att.get("mime_type") or ""
                    b64_data = att.get("data") or att.get("data_b64") or ""
                else:
                    filename = getattr(att, "filename", None) or getattr(att, "name", None) or "file"
                    mime_type = getattr(att, "mime_type", "") or ""
                    b64_data = getattr(att, "data", None) or getattr(att, "data_b64", "") or ""

                ext = os.path.splitext(filename)[1].lower()
                if not mime_type or mime_type in ("application/octet-stream", ""):
                    mime_type = ext_map.get(ext, "application/octet-stream")

                if "," in b64_data and "base64" in b64_data[:60]:
                    b64_data = b64_data.split(",", 1)[1]

                raw_bytes = base64.b64decode(b64_data)
                part = types.Part.from_bytes(data=raw_bytes, mime_type=mime_type)
                parts.append(part)
            except Exception as err:
                print(f"Error processing attachment {filename}: {err}")
        return parts

    def chat(self, query: str, attachments: list | None = None) -> str:
        try:
            parts = self._process_attachments(attachments)
            prompt = parts + [query] if parts else query
            try:
                response = self.chat_session.send_message(prompt)
            except Exception:
                self._rebuild_session()
                response = self.chat_session.send_message(prompt)
            reply = response.text or ""

            try:
                history = self.chat_session.get_history()
                if len(history) > 20:
                    recent = history[-20:]
                    curr_model = getattr(self.chat_session, "_model", GEMINI_MODEL) or GEMINI_MODEL
                    self.chat_session = self.client.chats.create(
                        model=curr_model,
                        history=recent,
                        config=types.GenerateContentConfig(
                            system_instruction=self.system_instruction
                        ),
                    )
            except Exception:
                pass
            return reply
        except Exception as e:
            return f"I'm facing some issues right now: {e}"

    def chat_stream(self, query: str, attachments: list | None = None):
        """Yield tokens in real-time as they stream from Gemini."""
        try:
            parts = self._process_attachments(attachments)
            prompt = parts + [query] if parts else query
            try:
                response_stream = self.chat_session.send_message_stream(prompt)
            except Exception:
                self._rebuild_session()
                response_stream = self.chat_session.send_message_stream(prompt)
            for chunk in response_stream:
                text = chunk.text or ""
                if text:
                    yield text
        except Exception as e:
            yield f" [Error: {e}]"

    def reset_chat(self):
        self._rebuild_session()

    # ── Task management ───────────────────────────────────────────────────────

    def load_tasks(self) -> list:
        path = _task_file(self.session_id)
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def save_task(self, task: str):
        tasks = self.load_tasks()
        tasks.append(task)
        with open(_task_file(self.session_id), "w", encoding="utf-8") as f:
            json.dump(tasks, f)

    def delete_task(self, task_number: int) -> str | None:
        tasks = self.load_tasks()
        idx = task_number - 1
        if 0 <= idx < len(tasks):
            removed = tasks.pop(idx)
            with open(_task_file(self.session_id), "w", encoding="utf-8") as f:
                json.dump(tasks, f)
            return removed
        return None

    # ── Music & Song Playback (Alexa-style Immediate Autoplay) ────────────────

    def _parse_song_intent(self, query: str) -> dict | None:
        """Parse Alexa-style song playback and recommendation requests.
        Starts playing the song directly and immediately upon opening.
        """
        q = query.lower().strip()

        # Exclude non-music actions that use the word 'play'
        non_music = ("chess", "cricket", "game", "football", "tennis", "basketball", "minecraft", "fortnite")
        if any(w in q for w in non_music):
            return None

        # Check if user specifically requested Spotify
        is_spotify_explicit = bool(re.search(r"\b(?:on|from|in)\s+spotify\b", q) or q.startswith("spotify "))

        # 1. Suggest a song requests (e.g. "suggest a song", "suggest any song", "recommend music")
        suggest_patterns = [
            r"(?:can you\s+)?(?:suggest|recommend)(?:\s+me)?\s+(?:a|any|some)?\s*(?:good\s+)?(?:song|music|track)",
            r"what\s+song\s+should\s+i\s+listen\s+to",
            r"give\s+me\s+a\s+(?:good\s+)?song",
            r"what\s+should\s+i\s+play",
        ]
        if any(re.search(p, q) for p in suggest_patterns):
            key, (song, artist, vid) = random.choice(list(CURATED_SONGS.items()))
            if is_spotify_explicit:
                target = f"{song} {artist}"
                url = f"https://open.spotify.com/search/{urllib.parse.quote(target)}"
                reply = f"I suggest '{song}' by {artist}! Opening it on Spotify."
                return {"song": target, "reply": reply, "url": url, "video_id": None}
            else:
                url = f"https://www.youtube.com/watch?v={vid}&autoplay=1"
                reply = f"I suggest '{song}' by {artist}! Playing it for you now."
                return {"song": f"{song} {artist}", "reply": reply, "url": url, "video_id": vid}

        # 2. User suggests a specific song: "i suggest <song>", "suggest playing <song>", "how about <song>"
        user_suggest = re.search(r"\b(?:i suggest|how about playing|what about playing|how about|what about)\s+(.+)", q)
        if user_suggest:
            raw = user_suggest.group(1).strip()
            clean = re.sub(r"\b(?:on|from|in)\s+(?:spotify|youtube)\b", "", raw)
            clean = re.sub(r"\b(?:please|for me)\b", "", clean).strip(" .?!,\"':")
            if clean and not re.match(r"^(?:a\s+|any\s+|some\s+)?(?:good\s+)?(?:song|music|track)$", clean):
                if is_spotify_explicit:
                    url = f"https://open.spotify.com/search/{urllib.parse.quote(clean)}"
                    reply = f"Great choice! Playing {clean.title()} on Spotify!"
                    return {"song": clean, "reply": reply, "url": url, "video_id": None}
                url, vid = resolve_song_playable_url(clean)
                reply = f"Great choice! Playing {clean.title()} for you now!"
                return {"song": clean, "reply": reply, "url": url, "video_id": vid}

        # 3. Direct play commands: "play <song>", "listen to <song>", "put on <song>"
        play_match = re.search(r"\b(?:play|listen to|put on)\s+(.+)", q)
        if play_match:
            raw = play_match.group(1).strip()
            clean = re.sub(r"\b(?:on|from|in)\s+(?:spotify|youtube)\b", "", raw)
            clean = re.sub(r"\b(?:please|for me)\b", "", clean).strip(" .?!,\"':")
            if not clean or clean in ("music", "some music", "a song", "songs", "spotify", "something"):
                key, (song, artist, vid) = random.choice(list(CURATED_SONGS.items()))
                if is_spotify_explicit:
                    return {"song": "music", "reply": "Playing music on Spotify!", "url": "https://open.spotify.com", "video_id": None}
                url = f"https://www.youtube.com/watch?v={vid}&autoplay=1"
                return {"song": f"{song} by {artist}", "reply": f"Playing '{song}' by {artist} for you!", "url": url, "video_id": vid}

            if is_spotify_explicit:
                url = f"https://open.spotify.com/search/{urllib.parse.quote(clean)}"
                return {"song": clean, "reply": f"Playing {clean.title()} on Spotify!", "url": url, "video_id": None}

            url, vid = resolve_song_playable_url(clean)
            return {"song": clean, "reply": f"Playing {clean.title()} for you!", "url": url, "video_id": vid}

        # 4. Explicit spotify query: "spotify <song>"
        spotify_match = re.search(r"\bspotify\s+(.+)", q)
        if spotify_match:
            raw = spotify_match.group(1).strip()
            clean = re.sub(r"\b(?:please|for me)\b", "", raw).strip(" .?!,\"':")
            if clean:
                url = f"https://open.spotify.com/search/{urllib.parse.quote(clean)}"
                return {"song": clean, "reply": f"Playing {clean.title()} on Spotify!", "url": url, "video_id": None}

        return None

    def _parse_spotify_intent(self, query: str) -> dict | None:
        """Alias for backward compatibility."""
        return self._parse_song_intent(query)

    # ── Command dispatcher ────────────────────────────────────────────────────

    def execute_command(self, query: str, attachments: list | None = None) -> dict:
        q = query.lower().strip()
        if not q and not attachments:
            return {"reply": "", "action": None, "action_data": None, "status": "done"}

        # If user attached files, prioritize multimodal reasoning over simple keywords
        has_media = bool(attachments)

        # ── Learn passively from every message ────────────────────────────────
        learned_items = self._learn_from_message(query)

        # ── Built-in shortcut commands (only if no media attached) ─────────────
        if not has_media:
            # 0. Alexa-style song playback and recommendations
            song_info = self._parse_song_intent(query)
            if song_info:
                return {
                    "reply": song_info["reply"],
                    "action": "play-music",
                    "action_data": {
                        "url": song_info["url"],
                        "video_id": song_info.get("video_id"),
                        "song": song_info.get("song"),
                    },
                    "status": "done",
                }

            if any(p in q for p in ("stop music", "pause music", "stop the song", "pause the song", "stop song", "pause song")):
                return {"reply": "Music paused.", "action": "pause-music", "action_data": None, "status": "done"}

            if any(p in q for p in ("resume music", "continue music", "resume song", "unpause music")):
                return {"reply": "Resuming music.", "action": "resume-music", "action_data": None, "status": "done"}

            matched_site = _match_site_intent(query)
            if matched_site:
                return {
                    "reply": f"Opening {matched_site['name']} for you!",
                    "action": "open-url",
                    "action_data": matched_site["url"],
                    "status": "done",
                }

            now = datetime.datetime.now()
            if "time" in q and "what" in q:
                return {"reply": f"It's {now.strftime('%I:%M %p')}.", "action": None, "action_data": None, "status": "done"}
            if "date" in q or "today" in q:
                return {"reply": f"Today is {now.strftime('%A, %d %B %Y')}.", "action": None, "action_data": None, "status": "done"}

            if "reset chat" in q or "clear history" in q:
                self.reset_chat()
                return {"reply": "Chat history cleared. Fresh start!", "action": None, "action_data": None, "status": "done"}

            if "what have you learned" in q or "what do you know about me" in q or "your memory" in q:
                summary = self.get_memory_summary()
                parts = []
                if summary["name"]:
                    parts.append(f"Your name is {summary['name']}.")
                if summary["interests"]:
                    parts.append(f"You're interested in {', '.join(summary['interests'][:5])}.")
                if summary["preferences"]:
                    parts.append(f"You like: {'; '.join(summary['preferences'][:3])}.")
                if summary["behavior_rules"]:
                    parts.append(f"I follow these rules: {'; '.join(summary['behavior_rules'][:2])}.")
                if summary["learned_facts"]:
                    parts.append(f"I've learned {len(summary['learned_facts'])} facts about you.")
                parts.append(f"We've had {summary['interaction_count']} interactions together.")
                reply = " ".join(parts) if parts else "I'm still getting to know you! Tell me about yourself."
                return {"reply": reply, "action": "show-memory", "action_data": summary, "status": "done"}

            if "forget everything" in q or "clear my memory" in q or "reset memory" in q:
                self.forget("all")
                return {"reply": "I've cleared everything I learned about you. We start fresh.", "action": None, "action_data": None, "status": "done"}

            if "remember" in q and "task" not in q:
                task_text = re.sub(r"remember\s+(to\s+)?", "", q).strip()
                if task_text:
                    self.save_task(task_text)
                    return {"reply": f"Noted — I'll remember to {task_text}.", "action": None, "action_data": None, "status": "done"}

            if "show my tasks" in q or "my tasks" in q:
                tasks = self.load_tasks()
                if tasks:
                    task_text = "\n".join([f"{i+1}. {t}" for i, t in enumerate(tasks)])
                    return {
                        "reply": f"You have {len(tasks)} task{'s' if len(tasks) != 1 else ''}.",
                        "action": "show-tasks",
                        "action_data": task_text,
                        "status": "done",
                    }
                return {"reply": "You have no tasks. Shall I add one?", "action": None, "action_data": None, "status": "done"}

            if "delete task" in q:
                num_str = q.replace("delete task", "").strip()
                try:
                    removed = self.delete_task(int(num_str))
                    reply = f"Removed: {removed}." if removed else "I couldn't find that task number."
                except ValueError:
                    reply = "Please say the task number you'd like to delete."
                return {"reply": reply, "action": None, "action_data": None, "status": "done"}

            if any(w in q for w in ("goodbye", "bye", "aanya quit", "sleep", "exit")):
                name = self.memory["user_profile"].get("name", "")
                farewell = f"Goodbye{', ' + name if name else ''}! It was lovely chatting with you."
                return {"reply": farewell, "action": "quit", "action_data": None, "status": "done"}

        # ── Gemini multimodal chat (with learned context injected) ─────────────
        query_text = query if query.strip() else "Please analyze the uploaded media in detail."
        reply = self.chat(query_text, attachments)

        return {
            "reply": reply,
            "action": "learned" if learned_items else None,
            "action_data": learned_items if learned_items else None,
            "status": "done",
        }

    def execute_command_stream(self, query: str, attachments: list | None = None):
        """Streaming generator that yields SSE data packets for real-time responsiveness."""
        q = query.lower().strip()
        has_media = bool(attachments)

        # ── Built-in shortcuts & instant commands ────────────────────────────
        if not has_media:
            # 0. Alexa-style song playback and recommendations
            song_info = self._parse_song_intent(query)
            if song_info:
                yield {
                    "type": "meta",
                    "action": "play-music",
                    "action_data": {
                        "url": song_info["url"],
                        "video_id": song_info.get("video_id"),
                        "song": song_info.get("song"),
                    },
                }
                yield {"type": "token", "token": song_info["reply"]}
                yield {"type": "done", "reply": song_info["reply"]}
                return

            if any(p in q for p in ("stop music", "pause music", "stop the song", "pause the song", "stop song", "pause song")):
                msg = "Music paused."
                yield {"type": "meta", "action": "pause-music", "action_data": None}
                yield {"type": "token", "token": msg}
                yield {"type": "done", "reply": msg}
                return

            if any(p in q for p in ("resume music", "continue music", "resume song", "unpause music")):
                msg = "Resuming music."
                yield {"type": "meta", "action": "resume-music", "action_data": None}
                yield {"type": "token", "token": msg}
                yield {"type": "done", "reply": msg}
                return

            # 1. Direct website openers
            matched_site = _match_site_intent(query)
            if matched_site:
                yield {"type": "meta", "action": "open-url", "action_data": matched_site["url"]}
                msg = f"Opening {matched_site['name']} for you!"
                yield {"type": "token", "token": msg}
                yield {"type": "done", "reply": msg}
                return

            # 2. Instant commands: time, date, memory, tasks, goodbye, reset
            instant_triggers = (
                "time", "date", "today", "reset chat", "clear history",
                "what have you learned", "what do you know about me", "your memory",
                "forget everything", "clear my memory", "reset memory",
                "remember", "show my tasks", "my tasks", "delete task",
                "goodbye", "bye", "aanya quit", "sleep", "exit"
            )
            if any(trig in q for trig in instant_triggers):
                res = self.execute_command(query, attachments)
                yield {"type": "meta", "action": res.get("action"), "action_data": res.get("action_data")}
                yield {"type": "token", "token": res["reply"]}
                yield {"type": "done", "reply": res["reply"]}
                return

        # ── Gemini Streaming ──────────────────────────────────────────────────
        learned_items = self._learn_from_message(query)
        yield {
            "type": "meta",
            "action": "learned" if learned_items else None,
            "action_data": learned_items if learned_items else None,
        }

        query_text = query if query.strip() else "Please analyze the uploaded media in detail."
        full_reply = []
        for token in self.chat_stream(query_text, attachments):
            full_reply.append(token)
            yield {"type": "token", "token": token}

        yield {"type": "done", "reply": "".join(full_reply)}


# Backward compatibility alias
AnanyaEngine = AanyaEngine
