# Aanya — Personal AI Voice Assistant

> A multi-modal personal AI assistant with adaptive memory, real-time voice recognition, and a beautiful pastel web interface. Powered by Google Gemini.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Setup & Installation](#setup--installation)
- [Running Aanya](#running-aanya)
- [API Reference](#api-reference)
- [Configuration](#configuration)
- [Site Quick-Open Rules](#site-quick-open-rules)
- [Adaptive Memory](#adaptive-memory)
- [Web UI Colour Themes](#web-ui-colour-themes)
- [Building the macOS Desktop App](#building-the-macos-desktop-app)
- [License](#license)

---

## Overview

Aanya is a personal voice assistant built with Python and Google Gemini. It runs in three modes:

| Mode | Entry Point | Interface |
|---|---|---|
| **Web** | `app.py` | Browser UI at `localhost:8000` |
| **CLI / Voice** | `main.py` | Terminal with mic input |
| **Desktop** | `desktop_app.py` | Native macOS CustomTkinter app |

All three modes share the same core AI engine (`server/engine.py`) and persistent adaptive memory.

---

## Features

- **Natural Language Understanding** — powered by `gemini-3.5-flash-lite` with streaming responses
- **Voice Recognition** — system microphone via `SpeechRecognition` + `sounddevice`
- **Text-to-Speech** — British-English audio via Google TTS (`gTTS`), streamed as MP3 to the browser
- **Adaptive Memory** — Aanya remembers your name, preferences, behavioral rules, and learned facts. She gets smarter with every thumbs-up/thumbs-down you give
- **Task Management** — Create, list, and delete persistent reminders by voice or text
- **File Analysis** — Attach images, PDFs, audio, and video; Gemini analyses them in context
- **Quick Site Opening** — Open GitHub, YouTube, Spotify, WhatsApp, Google, Wikipedia, and LeetCode by voice command
- **Real-time Streaming** — Server-Sent Events (SSE) stream tokens to the browser as they are generated
- **Pastel Web UI** — Clean interface with Bootstrap Icons, DM Sans/Inter typography, and three pastel colour themes (Lavender, Blush, Sage)

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                         Clients                              │
│  Browser (Web UI)  │  Terminal (main.py)  │  Desktop App     │
└────────┬───────────┴─────────┬────────────┴───────┬──────────┘
         │  HTTP / SSE          │ direct call         │ direct call
         ▼                     ▼                     ▼
┌─────────────────┐   ┌─────────────────────────────────────────┐
│  FastAPI (app.py)│   │          server/engine.py               │
│  /chat           │──▶│  AanyaEngine                            │
│  /chat/stream    │   │  ├─ execute_command()                   │
│  /tasks          │   │  ├─ execute_command_stream()            │
│  /memory         │   │  ├─ Adaptive Memory (JSON persistence)  │
│  /feedback       │   │  └─ Site intent matching                │
│  /tts            │   └─────────────┬───────────────────────────┘
└─────────────────┘                 │
                                    ▼
                          ┌──────────────────┐
                          │  Google Gemini   │
                          │  (genai SDK)     │
                          └──────────────────┘
```

**Memory persistence** — `server/data/<session_id>.json` stores the learning profile per session.

---

## Project Structure

```
Aanya/
├── app.py                  # FastAPI server — HTTP + SSE endpoints
├── main.py                 # CLI/Voice assistant engine + AanyaEngine class
├── desktop_app.py          # macOS CustomTkinter desktop GUI
├── config.py               # .env loader; exposes gemini_key, apikey
├── models.py               # Re-exports Pydantic models from server/
├── engine.py               # Thin re-export shim for app.py
├── openaitest.py           # OpenAI integration diagnostic utility
├── requirements.txt        # Python dependencies
├── Aanya.spec              # PyInstaller spec for macOS .app bundle
├── aanya.icns              # App icon
├── make_icns.py            # Icon generation helper
├── Procfile                # Heroku / Railway deploy config
├── .env                    # API keys (git-ignored)
│
├── server/
│   ├── engine.py           # Core AanyaEngine — AI, memory, streaming
│   ├── models.py           # Pydantic request/response models
│   └── data/               # Per-session memory JSON files (auto-created)
│
└── static/
    ├── index.html          # Web UI shell
    ├── style.css           # Pastel design system (CSS custom properties)
    ├── app.js              # Frontend controller (voice, chat, memory, tasks)
    └── orb.js              # Canvas fluid voice orb visualizer
```

---

## Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.11 or 3.12 recommended |
| pip / uv | latest |
| Google Gemini API key | **Required** |
| Microphone | Required for voice mode |
| macOS | Required for desktop app only |

---

## Setup & Installation

### 1. Clone the Repository

```bash
git clone https://github.com/Yuvika108/Aanya.git
cd Aanya
```

### 2. Create a Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

> **macOS note:** `sounddevice` requires PortAudio. Install it first:
> ```bash
> brew install portaudio
> ```

### 4. Configure API Keys

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your-gemini-api-key-here
OPENAI_API_KEY=your-openai-api-key-here   # optional, for openaitest.py
```

Get your free Gemini API key at [aistudio.google.com](https://aistudio.google.com/app/apikey).

---

## Running Aanya

### Web Interface (FastAPI)

```bash
python app.py
```

Or with uvicorn directly:

```bash
uvicorn app:app --reload --port 8000
```

| URL | Description |
|---|---|
| `http://localhost:8000/` | Web UI |
| `http://localhost:8000/docs` | Interactive Swagger API docs |
| `http://localhost:8000/api/health` | Health check |

### CLI / Voice Mode

```bash
python main.py
```

Aanya will listen for your voice via the microphone and respond in the terminal. Type `exit` or `quit` to stop.

### Desktop App

```bash
python desktop_app.py
```

---

## API Reference

### `POST /chat`

Send a message (optionally with file attachments). Returns a JSON response.

**Request:**
```json
{
  "session_id": "default",
  "message": "What time is it?",
  "attachments": []
}
```

**Response:**
```json
{
  "reply": "It's 3:42 PM.",
  "action": null,
  "action_data": null
}
```

**Actions** returned in the `action` field:

| Value | Description |
|---|---|
| `open-url` | Browser should open `action_data` URL |
| `learned` | New facts stored; `action_data` lists them |
| `show-memory` | Trigger the memory drawer in the UI |
| `show-tasks` | Trigger the tasks drawer in the UI |

---

### `POST /chat/stream`

Same payload as `/chat`. Returns a Server-Sent Events stream:

```
data: {"type": "token", "text": "It's "}
data: {"type": "token", "text": "3:42 PM."}
data: {"type": "done", "action": null, "action_data": null}
```

---

### `GET /tasks/{session_id}`

Returns the current task list.

### `POST /tasks/{session_id}`

Body: `{ "task": "Buy groceries" }`

### `DELETE /tasks/{session_id}/{task_number}`

Remove a task by its 1-based index.

---

### `GET /memory/{session_id}`

Returns everything Aanya has learned for the session.

### `DELETE /memory/{session_id}`

Wipes all adaptive memory for the session (irreversible).

---

### `POST /feedback`

```json
{
  "session_id": "default",
  "positive": false,
  "last_reply": "The capital of Australia is Sydney.",
  "correction": "Actually, it's Canberra."
}
```

---

### `POST /tts`

```json
{ "text": "Hello, how are you?", "slow": false }
```

Returns an `audio/mpeg` stream of British-accented speech.

---

## Configuration

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | **Yes** | Google Gemini API key |
| `OPENAI_API_KEY` | No | Only needed for `openaitest.py` |
| `PORT` | No | Server port (default: `8000`) |

The AI model is set in `server/engine.py`:

```python
GEMINI_MODEL = "gemini-3.5-flash-lite"
```

---

## Site Quick-Open Rules

Aanya recognises voice commands like *"Open GitHub"* or *"Open WhatsApp"* and launches the site in the browser. Aliases are defined in `SITE_RULES` inside `main.py` and `server/engine.py`:

| Site | Aliases |
|---|---|
| GitHub | `github`, `git hub`, `gethub` |
| WhatsApp | `whatsapp`, `whats app`, `what's app` |
| YouTube | `youtube`, `you tube` |
| Spotify | `spotify` |
| Google | `google` |
| Wikipedia | `wikipedia`, `wiki` |
| LeetCode | `leetcode`, `leet code` |

To add a new site, append to `SITE_RULES` in **both** `main.py` and `server/engine.py`:

```python
{
    "name": "Netflix",
    "aliases": ["netflix", "net flix"],
    "url": "https://www.netflix.com",
},
```

---

## Adaptive Memory

Memory is stored per-session as JSON in `server/data/`. It tracks:

| Field | How it's populated |
|---|---|
| **User Identity** | Phrases like *"My name is…"* |
| **Preferences & Likes** | Phrases like *"I like…"* or *"My favourite is…"* |
| **Behavioral Rules** | Phrases like *"Always…"* or *"Never…"* |
| **Learned Facts** | Corrections and *"Remember that…"* statements |
| **Detected Interests** | Topics inferred from conversation history |
| **Feedback Metrics** | Thumbs-up count, thumbs-down count, interaction count |

Use the thumbs-up / thumbs-down buttons in the web UI to teach Aanya. On a thumbs-down, you can type the correct answer — it is immediately committed to memory for the rest of the session.

---

## Web UI Colour Themes

Three pastel themes, selectable from Settings or cycled by the palette button in the header:

| Theme | Background | Accent |
|---|---|---|
| **Pastel Lavender** (default) | `hsl(250, 30%, 97%)` | `hsl(258, 68%, 62%)` |
| **Pastel Blush** | `hsl(340, 28%, 97%)` | `hsl(345, 62%, 60%)` |
| **Pastel Sage** | `hsl(145, 22%, 96%)` | `hsl(148, 48%, 45%)` |

---

## Building the macOS Desktop App

```bash
pip install pyinstaller
pyinstaller Aanya.spec
```

Output: `dist/Aanya.app` — a standalone double-click app with no Python dependency on the target machine.

---

## Testing the OpenAI Integration

`openaitest.py` is a standalone diagnostic that tests your OpenAI key without touching the main assistant:

```bash
python openaitest.py
```

---

## License

MIT License — © 2026 [Yuvika108](https://github.com/Yuvika108)

See [LICENSE](./LICENSE) for the full text.
