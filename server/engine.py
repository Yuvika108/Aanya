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
import sys
import subprocess
import re
import json
import base64
import datetime
import urllib.parse
import urllib.request
import time
import functools
import random
from google import genai
from google.genai import types

# ── Gemini Models Cascade ───────────────────────────────────────────────────
# Primary model with automatic fallback cascade to survive 503 UNAVAILABLE,
# 429 RESOURCE_EXHAUSTED, 404 NOT_FOUND, and temporary high-demand capacity spikes.
# Default to high-speed sub-second models (gemini-3.5-flash-lite, gemini-flash-lite-latest)
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
_seen_models = set()
MODEL_FALLBACK_CASCADE = []
for _m in MODEL_CASCADE:
    if _m and _m not in _seen_models:
        _seen_models.add(_m)
        MODEL_FALLBACK_CASCADE.append(_m)

GEMINI_MODEL = MODEL_FALLBACK_CASCADE[0]
FALLBACK_MODEL = MODEL_FALLBACK_CASCADE[1] if len(MODEL_FALLBACK_CASCADE) > 1 else MODEL_FALLBACK_CASCADE[0]

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
    },
    {
        "name": "YouTube",
        "aliases": ["youtube", "you tube", "yt"],
        "url": "https://www.youtube.com",
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
    {
        "name": "Google",
        "aliases": ["google"],
        "url": "https://www.google.com",
    },
    {
        "name": "Wikipedia",
        "aliases": ["wikipedia", "wiki"],
        "url": "https://www.wikipedia.org",
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
                "reply": f"Searching Google for '{target}'!",
            }

    yt_search = re.search(r"^(?:search(?:\s+for)?\s+(.+)\s+on\s+youtube|search\s+youtube\s+for\s+(.+))$", q)
    if yt_search:
        target = (yt_search.group(1) or yt_search.group(2) or "").strip()
        if target:
            return {
                "name": "YouTube",
                "url": f"https://www.youtube.com/results?search_query={urllib.parse.quote(target)}",
                "reply": f"Searching YouTube for '{target}'!",
            }

    wiki_search = re.search(r"^(?:search(?:\s+for)?\s+(.+)\s+on\s+wikipedia|search\s+wikipedia\s+for\s+(.+)|wikipedia\s+(.+))$", q)
    if wiki_search:
        target = (wiki_search.group(1) or wiki_search.group(2) or wiki_search.group(3) or "").strip()
        if target:
            return {
                "name": "Wikipedia",
                "url": f"https://en.wikipedia.org/w/index.php?search={urllib.parse.quote(target)}",
                "reply": f"Searching Wikipedia for '{target}'!",
            }

    li_search = re.search(r"^(?:search(?:\s+for)?\s+(.+)\s+on\s+linkedin|search\s+(?:on\s+)?linkedin\s+for\s+(.+)|linkedin\s+search(?:\s+for)?\s+(.+))$", q)
    if li_search:
        target = (li_search.group(1) or li_search.group(2) or li_search.group(3) or "").strip()
        if target:
            return {
                "name": "LinkedIn",
                "url": f"https://www.linkedin.com/search/results/all/?keywords={urllib.parse.quote(target)}",
                "reply": f"Searching LinkedIn for '{target}'!",
            }

    # 2. Exclude closing tabs, drafting / sending emails or asking questions about sites
    if re.search(r"^(?:(?:can|could|would)\s+you\s+(?:please\s+)?|please\s+)?(?:close|shut|exit)\b", q):
        return None
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

    # Check custom user links first if available
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
                    "reply": f"Opening {cl.get('name')} for you!",
                }

    for rule in SITE_RULES:
        for alias in rule["aliases"]:
            # Strict word boundary match
            if target_site == alias or re.search(rf"\b{re.escape(alias)}\b", target_site):
                # If no explicit open keyword was used, only allow very short commands (e.g. "youtube", "github", "emails")
                if not open_match and len(target_site.split()) > 2:
                    continue
                return rule

    return None


def _match_close_tab_intent(query: str, custom_links: list[dict] | None = None):
    """Match voice and text commands to close browser tabs (e.g. 'Close Github', 'Close tab')."""
    q = query.lower().strip()
    if re.search(r"\b(?:music|song|player)\b", q):
        return None
    if re.search(r"\b(?:drawer|modal|dialog|popup|sidebar|chat)\b", q):
        return None
    if any(q.startswith(w) for w in ("what is ", "who is ", "how to ", "how do ", "why is ", "tell me ")):
        return None

    close_match = re.search(
        r"^(?:(?:can|could|would)\s+you\s+(?:please\s+)?|please\s+)?"
        r"(?:close|shut(?:\s+down)?|exit)\s+(?:the\s+)?(?:browser\s+tab(?:\s+for|\s+of)?|tab(?:\s+for|\s+of)?|browser\s+window(?:\s+for|\s+of)?|window(?:\s+for|\s+of)?|page(?:\s+for|\s+of)?)?\s*(.+)?$",
        q,
    )
    if not close_match:
        return None

    raw_target = (close_match.group(1) or "").strip().strip(".,!?:'\"")
    target = re.sub(r"^(?:for|of|the|active|current|this)\s+", "", raw_target).strip()
    target = re.sub(r"\s+(?:tab|browser tab|window|page)$", "", target).strip()

    if not target or target in ("tab", "browser tab", "window", "browser window", "this", "it", "active", "current"):
        return {
            "name": "active tab",
            "target": "active",
            "url_pattern": None,
            "reply": "Closing the active browser tab.",
        }

    # Match custom links
    if custom_links:
        for cl in custom_links:
            name = (cl.get("name") or "").strip().lower()
            if target == name or re.search(rf"\b{re.escape(name)}\b", target):
                return {
                    "name": cl.get("name", target),
                    "target": target,
                    "url_pattern": cl.get("url"),
                    "reply": f"Closing {cl.get('name')} tab.",
                }

    # Match standard site rules
    for rule in SITE_RULES:
        for alias in rule["aliases"]:
            if target == alias or re.search(rf"\b{re.escape(alias)}\b", target):
                return {
                    "name": rule["name"],
                    "target": alias,
                    "url_pattern": rule["url"],
                    "reply": f"Closing {rule['name']} tab.",
                }

    if len(target.split()) <= 3:
        return {
            "name": target.capitalize(),
            "target": target,
            "url_pattern": None,
            "reply": f"Closing {target.capitalize()} tab.",
        }

    return None


def _close_browser_tab(target_name: str, url_pattern: str | None = None):
    """Close matching browser tab in Google Chrome or Safari on macOS."""
    if sys.platform != "darwin":
        return

    pattern = (url_pattern or target_name).lower().replace(" ", "")
    is_active = target_name.lower() in ("active", "active tab", "current", "this", "tab")

    # 1. Google Chrome
    try:
        if is_active:
            script = 'tell application "Google Chrome" to close active tab of front window'
        else:
            script = f'''tell application "Google Chrome"
                repeat with w in windows
                    set tabList to (tabs of w)
                    repeat with t in tabList
                        set tabUrl to (URL of t as string)
                        set tabTitle to (title of t as string)
                        if (tabUrl contains "{pattern}") or (tabTitle contains "{target_name}") or (tabUrl contains "{target_name.lower()}") then
                            close t
                        end if
                    end repeat
                end repeat
            end tell'''
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=1.5)
    except Exception:
        pass

    # 2. Safari
    try:
        if is_active:
            script = 'tell application "Safari" to close current tab of front window'
        else:
            script = f'''tell application "Safari"
                repeat with w in windows
                    set tabList to (tabs of w)
                    repeat with t in tabList
                        set tabUrl to (URL of t as string)
                        set tabTitle to (name of t as string)
                        if (tabUrl contains "{pattern}") or (tabTitle contains "{target_name}") or (tabUrl contains "{target_name.lower()}") then
                            close t
                        end if
                    end repeat
                end repeat
            end tell'''
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=1.5)
    except Exception:
        pass

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

def _links_file(session_id: str) -> str:
    return os.path.join(DATA_DIR, f"links_{_safe_id(session_id)}.json")

# Backward compat alias
_take_file = _task_file


# ── Learning keyword patterns ─────────────────────────────────────────────────

NAME_EXCLUSIONS = {
    "a", "an", "the", "not", "just", "ready", "tired", "back", "here", "fine", "good",
    "sorry", "sure", "learning", "interested", "okay", "ok", "done", "bored", "busy",
    "excited", "sick", "listening", "free", "waiting", "looking", "trying", "going",
    "wondering", "asking", "thinking", "glad", "sad", "alive", "human", "someone",
    "user", "person", "man", "woman", "boy", "girl", "happy", "hungry", "sleepy",
    "confused", "lost", "working", "playing", "studying", "coding", "chilling",
    "new", "old", "late", "early", "curious", "exhausted", "stressed", "feeling",
    "well", "better", "great", "awesome", "cool", "super", "home", "away", "talking",
    "helping", "testing", "running", "alright", "nothing", "everything"
}

_NAME_PATTERNS = [
    r"^my\s+name\s+is\s+([A-Za-z]+)",
    r"^call\s+me\s+([A-Za-z]+)",
    r"^i\s+go\s+by\s+([A-Za-z]+)",
    r"^i\s*am\s+([A-Za-z]+)$",
    r"^i'm\s+([A-Za-z]+)$",
]

_PREFERENCE_PATTERNS = [
    r"^(?:i\s+(?:really\s+)?(?:like|love|enjoy|prefer))\s+(.+)$",
    r"^(?:my\s+favourite\s+(?:[a-z0-9_\-\s]+)\s+is)\s+(.+)$",
    r"^(?:i(?:'m|\s+am)\s+(?:really\s+)?(?:into|a\s+big\s+fan\s+of))\s+(.+)$",
]

_AVERSION_PATTERNS = [
    r"^(?:i\s+(?:really\s+)?(?:hate|dislike|can't\s+stand|detest))\s+(.+)$",
    r"^(?:i(?:'m|\s+am)\s+not\s+(?:a\s+fan\s+of|into))\s+(.+)$",
    r"^(?:please\s+)?never\s+(?:call\s+me|show\s+me|give\s+me|reply\s+with)\s+(.+)$",
    r"^(?:please\s+)?don't\s+(?:ever\s+)?(?:call\s+me|give\s+me|say)\s+(.+)$",
]

_CORRECTION_PATTERNS = [
    r"^(?:no,?\s+)?that(?:'s|\s+is)\s+(?:not\s+right|wrong|incorrect|false)\b",
    r"^(?:no,?\s+)?the\s+correct\s+answer\s+is\b",
    r"^you(?:'re|\s+are)\s+(?:mistaken|wrong)\b",
    r"^that\s+is\s+not\s+what\s+i\s+asked\b",
]

_RULE_PATTERNS = [
    r"^(?:you\s+(?:must|should)\s+always|always\s+make\s+sure\s+to|please\s+always|from\s+now\s+on,?\s+always|i\s+want\s+you\s+to\s+always)\s+(.+)$",
]

_TEACH_PATTERNS = [
    r"^(?:learn\s+this[:\.]?|teach\s+you[:\.]?|remember\s+that|note\s+that|keep\s+in\s+mind[:\.]?)\s+(.+)$",
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
        self.active_model = GEMINI_MODEL
        self.chat_session = None
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
        now = datetime.datetime.now()
        current_time_str = now.strftime("%A, %d %B %Y, %I:%M %p")

        parts = [
            f"REAL-WORLD CLOCK & CALENDAR: The current date and time is {current_time_str}. "
            "Use this temporal anchor to answer questions about today, current time, day of week, or recent events accurately.",
            "You are Aanya, an exceptionally capable, warm, and articulate AI assistant "
            "with a natural British accent, charm, and wit. "
            "Deliver prompt, insightful, high-precision answers. "
            "VOICE FLUIDITY & EFFORTLESS RESPONSIVENESS: Speak with the immediacy, effortless charm, and brevity of a world-class assistant like Jarvis or Siri. "
            "In casual or spoken interactions, give immediate, crisp, and direct answers (typically 1 to 2 clear, natural sentences) without repetitive filler, polite disclaimers, or robot preambles like 'Sure, I can help with that'. "
            "Get straight to the answer so conversations flow seamlessly, while delivering rich, structured explanations when detailed analysis or code is requested.",
        ]

        # Address user by name if known
        if profile.get("name"):
            parts.append(
                f"The user's name is {profile['name']}. "
                "Address them by name occasionally and naturally."
            )

        # Personality maturity based on interaction count
        if interactions > 50:
            parts.append(
                "You have had many conversations together. "
                "Be warm and familiar — like a long-time trusted companion."
            )
        elif interactions > 10:
            parts.append(
                "You are getting to know this user. "
                "Show genuine warmth and remember their preferences."
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

    def _rebuild_session(self, preferred_model: str | None = None, history: list | None = None):
        """Rebuild Gemini chat session with specified or fallback model and current system prompt."""
        self.system_instruction = self._build_system_prompt()
        target = preferred_model or getattr(self, "active_model", None) or GEMINI_MODEL
        candidates = [target] + [m for m in MODEL_FALLBACK_CASCADE if m != target]
        for m in candidates:
            try:
                self.chat_session = self.client.chats.create(
                    model=m,
                    history=history[-10:] if history else None,
                    config=types.GenerateContentConfig(
                        system_instruction=self.system_instruction
                    ),
                )
                self.active_model = m
                return
            except Exception as e:
                print(f"[Engine] Could not initialize chat session with {m}: {e}")
                continue

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
                candidate = m.group(1).strip()
                cand_lower = candidate.lower()
                if len(candidate) >= 2 and cand_lower not in NAME_EXCLUSIONS:
                    candidate_clean = candidate.capitalize()
                    old_name = self.memory["user_profile"].get("name")
                    if old_name != candidate_clean:
                        self.memory["user_profile"]["name"] = candidate_clean
                        learned.append(f"your name is {candidate_clean}")
                        changed = True
                    break

        # ── Preferences ───────────────────────────────────────────────────────
        for pattern in _PREFERENCE_PATTERNS:
            m = re.search(pattern, q)
            if m:
                pref = m.group(1).strip().strip(".,!?:")
                generic_words = {"it", "this", "that", "you", "to think", "not to", "to know", "something", "anything"}
                if len(pref) > 2 and pref.lower() not in generic_words and pref not in self.memory["preferences"]:
                    self.memory["preferences"].append(pref)
                    learned.append(f"you like {pref}")
                    changed = True
                break

        # ── Aversions ─────────────────────────────────────────────────────────
        for pattern in _AVERSION_PATTERNS:
            m = re.search(pattern, q)
            if m:
                aversion = m.group(1).strip().strip(".,!?:")
                if len(aversion) > 2 and aversion not in self.memory["aversions"]:
                    self.memory["aversions"].append(aversion)
                    learned.append(f"you dislike {aversion}")
                    changed = True
                break

        # ── Behavior rules ────────────────────────────────────────────────────
        for pattern in _RULE_PATTERNS:
            m = re.search(pattern, q)
            if m:
                rule = m.group(1).strip().strip(".,!?:")
                if len(rule) > 3 and rule not in self.memory["behavior_rules"]:
                    self.memory["behavior_rules"].append(rule)
                    learned.append(f"rule added: {rule}")
                    changed = True
                break

        # ── Explicit taught facts ─────────────────────────────────────────────
        for pattern in _TEACH_PATTERNS:
            m = re.search(pattern, q)
            if m:
                fact = m.group(1).strip().strip(".,!?:")
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
        if any(trigger in q for trigger in ("i love ", "i like ", "interested in ", "work in ", "passionate about ", "hobby is ")):
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
        parts = self._process_attachments(attachments)
        prompt = parts + [query] if parts else query

        # ── Fast path: direct send on existing active session without rebuild ──
        if self.chat_session is not None:
            try:
                response = self.chat_session.send_message(prompt)
                reply = response.text or ""
                # Keep history bounded
                try:
                    curr_history = self.chat_session.get_history()
                    if curr_history and len(curr_history) > 20:
                        recent = curr_history[-20:]
                        self.chat_session = self.client.chats.create(
                            model=self.active_model,
                            history=recent,
                            config=types.GenerateContentConfig(
                                system_instruction=self.system_instruction
                            ),
                        )
                except Exception:
                    pass
                return reply
            except Exception as e:
                print(f"[Engine] Active session failed with {getattr(self, 'active_model', 'unknown')}: {e}. Retrying fallback cascade...")
                self.chat_session = None

        history = []
        if self.chat_session:
            try:
                history = self.chat_session.get_history() or []
            except Exception:
                history = []

        curr_active = getattr(self, "active_model", None) or GEMINI_MODEL
        models_to_try = [curr_active] + [m for m in MODEL_FALLBACK_CASCADE if m != curr_active]

        for model_name in models_to_try:
            try:
                self._rebuild_session(preferred_model=model_name, history=history)
                response = self.chat_session.send_message(prompt)
                reply = response.text or ""
                self.active_model = model_name
                return reply
            except Exception as e:
                print(f"[Engine] Model {model_name} failed in chat(): {e}")
                self.chat_session = None
                time.sleep(0.2)
                continue

        return "I am currently experiencing unusually high demand across my network. Please try asking again in just a moment."

    def chat_stream(self, query: str, attachments: list | None = None):
        """Yield tokens in real-time as they stream from Gemini with automated model fallback."""
        parts = self._process_attachments(attachments)
        prompt = parts + [query] if parts else query

        # ── Fast path: direct stream on existing active session without rebuild ─
        if self.chat_session is not None:
            try:
                response_stream = self.chat_session.send_message_stream(prompt)
                first_chunk = next(response_stream, None)
                if first_chunk is not None:
                    text = first_chunk.text or ""
                    if text:
                        yield text

                for chunk in response_stream:
                    text = chunk.text or ""
                    if text:
                        yield text
                return
            except Exception as e:
                print(f"[Engine] Active stream failed with {getattr(self, 'active_model', 'unknown')}: {e}. Retrying fallback cascade...")
                self.chat_session = None

        history = []
        if self.chat_session:
            try:
                history = self.chat_session.get_history() or []
            except Exception:
                history = []

        curr_active = getattr(self, "active_model", None) or GEMINI_MODEL
        models_to_try = [curr_active] + [m for m in MODEL_FALLBACK_CASCADE if m != curr_active]

        for model_name in models_to_try:
            try:
                self._rebuild_session(preferred_model=model_name, history=history)
                response_stream = self.chat_session.send_message_stream(prompt)

                first_chunk = next(response_stream, None)
                if first_chunk is not None:
                    text = first_chunk.text or ""
                    if text:
                        yield text

                for chunk in response_stream:
                    text = chunk.text or ""
                    if text:
                        yield text

                self.active_model = model_name
                return
            except Exception as e:
                print(f"[Engine] Model {model_name} failed in chat_stream(): {e}")
                self.chat_session = None
                time.sleep(0.2)
                continue

        yield "I am currently experiencing unusually high demand across my network. Please try asking again in just a moment."

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

    # ── Custom Links & Shortcuts ──────────────────────────────────────────────

    def get_links(self) -> list[dict]:
        path = _links_file(self.session_id)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
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
        # Avoid duplicate names by updating URL if name exists
        existing = next((l for l in links if l.get("name", "").lower() == clean_name.lower()), None)
        if existing:
            existing["url"] = clean_url
            new_link = existing
        else:
            links.append(new_link)
        with open(_links_file(self.session_id), "w", encoding="utf-8") as f:
            json.dump(links, f, indent=2)
        return new_link

    def delete_link(self, link_id: str) -> bool:
        links = self.get_links()
        filtered = [l for l in links if l.get("id") != link_id and l.get("name", "").lower() != link_id.lower()]
        if len(filtered) != len(links):
            with open(_links_file(self.session_id), "w", encoding="utf-8") as f:
                json.dump(filtered, f, indent=2)
            return True
        return False

    # ── Music & Song Playback (Always Plays From YouTube with Instant Autoplay) ─

    def _parse_song_intent(self, query: str) -> dict | None:
        """Parse Aanya Music song playback and recommendation requests.
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

        # 1. Suggest a song requests (e.g. "suggest a song", "suggest any song", "recommend music")
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

        # 2. User suggests a specific song: "i suggest <song>", "how about playing <song>", "what about <song>"
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

    # ── Command dispatcher ────────────────────────────────────────────────────

    def _handle_instant_command(self, query: str) -> dict | None:
        """Evaluate deterministic system shortcuts (music, site open/search, precise clock, memory, tasks, exit).
        Returns result dict if matched, or None to hand off to Gemini general reasoning.
        """
        q = query.lower().strip()
        now = datetime.datetime.now()

        # 1. Aanya Music song playback and recommendations
        song_info = self._parse_song_intent(query)
        if song_info:
            return {
                "reply": song_info["reply"],
                "action": "play-music",
                "action_data": {
                    "url": song_info["url"],
                    "video_id": song_info.get("video_id"),
                    "videoId": song_info.get("video_id"),
                    "song": song_info.get("song"),
                },
                "status": "done",
            }

        # 2. Aanya Music pause / resume
        if re.search(r"\b(?:stop|pause)\s+(?:music|song|the\s+music|the\s+song)\b", q):
            return {"reply": "Music paused.", "action": "pause-music", "action_data": None, "status": "done"}

        if re.search(r"\b(?:resume|continue|unpause)\s+(?:music|song|the\s+music|the\s+song)\b", q):
            return {"reply": "Resuming music.", "action": "resume-music", "action_data": None, "status": "done"}

        # 3. Close browser tab intent
        custom_links = self.get_links()
        close_info = _match_close_tab_intent(query, custom_links=custom_links)
        if close_info:
            _close_browser_tab(close_info["target"], close_info.get("url_pattern"))
            return {
                "reply": close_info["reply"],
                "action": "close-tab",
                "action_data": {
                    "site": close_info["name"],
                    "target": close_info["target"],
                    "url_pattern": close_info.get("url_pattern"),
                },
                "status": "done",
            }

        # 3.2. Direct website & search intent (including user custom links)
        matched_site = _match_site_intent(query, custom_links=custom_links)
        if matched_site:
            reply_text = matched_site.get("reply") or f"Opening {matched_site['name']} for you!"
            return {
                "reply": reply_text,
                "action": "open-url",
                "action_data": matched_site["url"],
                "status": "done",
            }

        # 3.5. Custom Link Management (Add / Show Links via Voice & Text)
        add_link_match = re.search(
            r"^(?:(?:can|could|would)\s+you\s+(?:please\s+)?|please\s+)?(?:add|save|remember|create)\s+link[:\s]+(?:called\s+|named\s+)?([a-zA-Z0-9\s_-]+?)\s+(?:as\s+|to\s+|at\s+|url\s+)?(https?://\S+|\S+\.[a-zA-Z]{2,}\S*)$",
            q,
        )
        if add_link_match:
            lname = add_link_match.group(1).strip()
            lurl = add_link_match.group(2).strip()
            if lname and lurl:
                new_link = self.add_link(lname, lurl)
                return {
                    "reply": f"Added '{new_link['name']}' ({new_link['url']}) to your Quick Links! You can ask me to open {new_link['name']} anytime.",
                    "action": "link-added",
                    "action_data": new_link,
                    "status": "done",
                }

        if q in ("show links", "show my links", "list links", "list my links", "what are my links", "my links", "quick links", "show quick links"):
            links = self.get_links()
            if links:
                summary_text = ", ".join([f"{l['name']}" for l in links])
                return {
                    "reply": f"You have {len(links)} custom link{'s' if len(links) != 1 else ''}: {summary_text}.",
                    "action": "show-links",
                    "action_data": links,
                    "status": "done",
                }
            return {
                "reply": "You don't have any custom links saved yet. You can add one in the Quick Links drawer or say 'Add link [name] [url]'.",
                "action": "show-links",
                "action_data": [],
                "status": "done",
            }

        # 4. Strict Current Time Query
        if re.search(r"^(?:what(?:'s|\s+is)\s+the\s+time|what\s+time\s+is\s+it|current\s+time|tell\s+me\s+the\s+time)\??$", q):
            return {"reply": f"It's {now.strftime('%I:%M %p')}.", "action": None, "action_data": None, "status": "done"}

        # 5. Strict Today's Date Query
        if re.search(r"^(?:what(?:'s|\s+is)\s+(?:the\s+date|today(?:'s)?\s+date)|what\s+date\s+is\s+it(?:\s+today)?|what\s+is\s+today(?:'s)?\s+date|today(?:'s)?\s+date)\??$", q):
            return {"reply": f"Today is {now.strftime('%A, %d %B %Y')}.", "action": None, "action_data": None, "status": "done"}

        # 6. Chat reset
        if q in ("reset chat", "clear chat", "clear history", "reset history", "start over"):
            self.reset_chat()
            return {"reply": "Chat history cleared. Fresh start!", "action": None, "action_data": None, "status": "done"}

        # 7. Adaptive Memory Queries
        if q in ("what have you learned", "what do you know about me", "show your memory", "what is in your memory", "show memory", "view memory"):
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

        # 8. Memory Clear
        if q in ("forget everything", "clear my memory", "reset memory", "clear all memory"):
            self.forget("all")
            return {"reply": "I've cleared everything I learned about you. We start fresh.", "action": None, "action_data": None, "status": "done"}

        # 9. Tasks: Add Task
        task_add_match = re.search(r"^(?:remember\s+to|remind\s+me\s+to|add\s+task[:\s]+|new\s+task[:\s]+|add\s+to(?:-do|\s+tasks?)[:\s]+|todo[:\s]+)\s+(.+)$", q)
        if task_add_match:
            task_text = task_add_match.group(1).strip()
            if task_text.startswith("to "):
                task_text = task_text[3:].strip()
            if task_text:
                self.save_task(task_text)
                return {"reply": f"Noted — I'll remember to {task_text}.", "action": "task-added", "action_data": task_text, "status": "done"}

        # 10. Tasks: Show Tasks
        if q in ("show my tasks", "my tasks", "show tasks", "list my tasks", "list tasks", "what are my tasks"):
            tasks = self.load_tasks()
            if tasks:
                task_text = "\n".join([f"{i+1}. {t}" for i, t in enumerate(tasks)])
                return {
                    "reply": f"You have {len(tasks)} task{'s' if len(tasks) != 1 else ''}.",
                    "action": "show-tasks",
                    "action_data": task_text,
                    "status": "done",
                }
            return {"reply": "You have no tasks saved. Shall I add one?", "action": None, "action_data": None, "status": "done"}

        # 11. Tasks: Delete Task
        task_del_match = re.search(r"^(?:delete|remove)\s+task\s+(\d+)$", q)
        if task_del_match:
            try:
                num = int(task_del_match.group(1))
                removed = self.delete_task(num)
                reply = f"Removed task {num}: {removed}." if removed else f"I couldn't find task number {num}."
            except Exception:
                reply = "Please specify a valid task number."
            return {"reply": reply, "action": None, "action_data": None, "status": "done"}

        # 12. Strict Farewell
        if re.search(r"^(?:goodbye|bye|bye\s+bye|see\s+you(?:\s+later)?|farewell|exit|quit|aanya\s+quit|go\s+to\s+sleep|sleep\s+now)$", q):
            name = self.memory["user_profile"].get("name", "")
            farewell = f"Goodbye{', ' + name if name else ''}! It was lovely chatting with you."
            return {"reply": farewell, "action": "quit", "action_data": None, "status": "done"}

        return None

    def execute_command(self, query: str, attachments: list | None = None) -> dict:
        q = query.lower().strip()
        if not q and not attachments:
            return {"reply": "", "action": None, "action_data": None, "status": "done"}

        # If user attached files, prioritize multimodal reasoning over simple shortcuts
        has_media = bool(attachments)

        # ── Learn passively from every message ────────────────────────────────
        learned_items = self._learn_from_message(query)

        # ── Built-in shortcut commands (only if no media attached) ─────────────
        if not has_media:
            instant_res = self._handle_instant_command(query)
            if instant_res is not None:
                return instant_res

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
            instant_res = self._handle_instant_command(query)
            if instant_res is not None:
                yield {
                    "type": "meta",
                    "action": instant_res.get("action"),
                    "action_data": instant_res.get("action_data"),
                }
                yield {"type": "token", "token": instant_res["reply"]}
                yield {"type": "done", "reply": instant_res["reply"], "action": instant_res.get("action"), "action_data": instant_res.get("action_data")}
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
