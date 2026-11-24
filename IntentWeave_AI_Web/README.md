# IntentWeave AI: A Context-Aware Multimodal Assistant

A runnable **Python + Streamlit web application** based on the supplied CSA1719 Artificial Intelligence capstone PPT. The UI and functionality correspond to three project modules:

1. **Multimodal Command Recognition** — text, browser-recorded voice, JPG/JPEG/PNG uploads, webcam capture, OpenCV image measurements, optional transcription, and browser speech output.
2. **Contextual Intent Reasoning** — command classification, follow-up question handling, conversation history, and optional AI model answers.
3. **Verified Action Execution** — proposal validation, explicit approval/cancellation, SQLite-backed tasks and notes, and action history.

## Start in VS Code on Windows

1. Extract this ZIP and open its `IntentWeave_AI_Web` folder in **Visual Studio Code**.
2. Install **Python 3.10+** (Python 3.11 or 3.12 recommended) and the VS Code Python extension.
3. Open **Terminal → New Terminal**.
4. Run:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   .\.venv\Scripts\python.exe -m streamlit run app.py
   ```

5. Open the local URL shown in your terminal, usually **http://localhost:8501**.

**Alternative:** double-click `run_windows.bat` to create the environment, install dependencies, and start the app. It uses the project-local `.venv` interpreter for both installation and launch.

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## AI features (optional)

The project **runs without any paid API key**. For more capable chat answers, object-level image understanding, and reliable speech-to-text:

1. Copy `.env.example` to a new file named `.env`.
2. Fill `OPENAI_API_KEY=your_key_here` in `.env`.
3. Restart the Streamlit app.

The demo defaults to the configurable `gpt-4o-mini` chat model and `whisper-1` transcription model. API usage may incur charges. **Never commit or share `.env`.** Open-ended AI answers and image questions use the provider; local pattern classification does not claim model-level semantic understanding or expose confidence scores.

Without a key, recorded speech attempts Google speech recognition (needs internet; may not always be available), and images use honest OpenCV measurements and optional OCR instead of invented object labels. OCR additionally requires installation of the **Tesseract OCR executable** on your computer; otherwise OCR is skipped without breaking the app.

## Commands to try

| Command | What happens |
| --- | --- |
| `What is Module 1?` | Explains input handling from the PPT |
| `What does Module 2 do?` | Explains contextual reasoning |
| `Add a task to prepare the project demo` | **Asks permission** before saving a task |
| `Show my tasks` | Reads stored tasks |
| `Mark it done` | Proposes completion of the most recent open task |
| `Save a note: check microphone permissions` | **Asks permission** before saving a note |
| `Show my notes` | Reads stored notes |
| `Calculate (125 + 75) / 4` | Safely evaluates arithmetic |
| `Summarize our conversation` | Lists recent user requests |
| Upload an image + `Analyze this image` | OpenCV measurements; optional AI visual Q&A |
| Record a voice message | Transcribes then processes the text when online |

## App navigation

- **Home** — project introduction, module pipeline, and session metrics.
- **AI Assistant / Multimodal Input** — chat, voice/image composer, local analysis preview, expandable processing trace, and approval controls.
- **Context Memory** — saved conversation turns and their input modalities.
- **Action Center** — tasks, notes, proposal confirmation, and action history.
- **Analytics** — persisted command, modality, intent, action, and recent-interaction summaries.
- **Demo Mode** — six guided scenarios; prompts invoke the actual processing flow and actions still require approval.
- **About Project** — project architecture, objectives, technologies, limitations, and future scope.
- **Settings** — AI connectivity, JSON export, conversation deletion, and privacy notes.

## Folder layout

```text
IntentWeave_AI_Web/
├── app.py                 # Streamlit user interface
├── engine.py              # Intent reasoning, arithmetic, approved operations
├── media.py               # Image analysis, audio transcription, optional AI
├── database.py            # SQLite conversations, messages, tasks, notes and logs
├── requirements.txt
├── .env.example           # Optional cloud API configuration
├── .streamlit/config.toml # Theme
├── run_windows.bat
├── tests/test_engine.py
├── tests/test_media.py
├── DEMO_GUIDE.md
├── TESTING.md
└── README.md
```

## What is real vs optional

**Runs locally:** UI, rule-based text intent detection, saved conversation context, task and note management with explicit approval, audit log, safe arithmetic, image resolution/brightness/color/edge measurements, conversation export, analytics, and browser speech synthesis when supported by the browser.

**Requires a service:** open-ended model chat, visual understanding beyond numeric OpenCV measurements, and speech transcription. Free Google speech recognition is attempted without an AI key, but still needs internet. The app does not claim to verify web facts or execute arbitrary commands.

**Demo limitations:** one local-user database, no authentication, no arbitrary operating-system execution, no background reminders, no image/audio byte retention, and no automatic online fact checking. This is an academic prototype, not a production-ready assistant.

The analytics page reads actual saved records from SQLite; it does not add seeded sample activity. Historical action transitions are retained in the audit trail, while pending approval counts reflect the latest state of each current request.

## Guided faculty demo

Follow [DEMO_GUIDE.md](./DEMO_GUIDE.md) for a click-by-click five-minute workflow. Test outcomes and coverage are recorded in [TESTING.md](./TESTING.md).

## Running tests

From the project folder, install `pytest` if necessary and run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The suite covers intent recognition, safe arithmetic, local action confirmation, conversation
separation, analytics, legacy SQLite migration, image decoding, and invalid image handling.

## Streamlit Cloud

- Main file: `app.py`
- Python dependencies: `requirements.txt`
- Set `OPENAI_API_KEY` in Streamlit Secrets only if AI or cloud transcription features are needed.
- Optional secret format:

  ```toml
  OPENAI_API_KEY = "replace-with-a-server-side-key"
  OPENAI_CHAT_MODEL = "gpt-4o-mini"
  OPENAI_TRANSCRIBE_MODEL = "whisper-1"
  ```

Local SQLite data is ephemeral in hosted deployments unless a persistent mounted database is
configured through `INTENTWEAVE_DB`. Do not treat Streamlit's hosted filesystem as permanent
storage. Public users do not need authentication for this academic demo, but production use would
require it.

## Troubleshooting

- **`py` not recognized:** install Python from python.org and enable the Windows launcher, or substitute `python` for `py`.
- **`streamlit` not recognized:** use `.venv\Scripts\python.exe -m streamlit run app.py`.
- **Microphone unavailable:** allow microphone permissions in your browser and Windows privacy settings; access through localhost.
- **Voice failed:** check internet connectivity or configure `OPENAI_API_KEY`.
- **No OCR text:** Tesseract is an optional external executable; without it the image metrics still work.
- **AI returned an HTTP error:** verify the API key, model access, quota, and network.
- **Python dependency issue:** recreate `.venv` with Python 3.11 or 3.12, then reinstall requirements.

Built specifically to match the supplied **IntentWeave AI** presentation. All API keys remain server-side in `.env`.
