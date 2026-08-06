# Aanya

Aanya is a macOS desktop AI voice assistant built with Python, CustomTkinter, Gemini AI, and speech recognition. It provides a polished chat UI, voice interaction, app launch shortcuts, task persistence, and AI-powered responses.

## Features

- Voice assistant UI using `customtkinter`
- Speech-to-text with `SpeechRecognition`
- Text-to-speech using macOS `say`
- Gemini AI chat integration via `google-genai`
- Quick launch shortcuts for websites and macOS apps
- Persistent task saving to `~/.aanya/tasks.txt`
- PyInstaller packaging support via `Aanya.spec`

## Project Structure

- `app.py` — Desktop UI and application shell
- `main.py` — Assistant engine, voice/chat logic, Gemini integration
- `config.py` — API key configuration
- `Aanya.spec` — PyInstaller spec for bundling the app
- `openaitest.py` — Example OpenAI chat test script
- `make_icns.py` — Icon generation helper

## Requirements

Install dependencies using pip:

```bash
pip install customtkinter pillow SpeechRecognition google-genai openai
```

Additional macOS requirements:

- Python 3.11+ recommended
- Microphone support for `SpeechRecognition`
- `PyAudio` or another supported audio backend if required by `SpeechRecognition`

## Configuration

Update `config.py` with your API keys:

```python
apikey = "<your-openai-api-key>"
gemini_key = "<your-gemini-api-key>"
```

> Important: Do not commit API keys to public repositories.

## Running the app

Start the application with:

```bash
python app.py
```

The app launches a desktop interface and connects the voice assistant engine from `main.py`.

## Packaging

A PyInstaller spec file is included as `Aanya.spec` for building a macOS app bundle:

```bash
pyinstaller Aanya.spec
```

## Notes

- The assistant uses the macOS `open` command to launch URLs and applications.
- The backend uses Gemini via `google.genai` and saves generated responses under `~/.aanya/GeminiResponses`.

## License

This repository does not include a license file. Add one if you want to share or distribute the project.
