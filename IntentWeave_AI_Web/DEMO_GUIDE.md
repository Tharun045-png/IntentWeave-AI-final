# IntentWeave AI — Five-minute faculty demonstration

## Before the demonstration

1. Start the app using `run_windows.bat` or the Windows commands in [README.md](./README.md).
2. Open **Home** and explain the three-stage pipeline: recognize, reason, verify.
3. If demonstrating cloud answers or image questions, configure the API key in `.env` beforehand and check the provider account/network. Never show the key. Without it, use the local limitations honestly.
4. For voice, use a browser on `localhost`, permit microphone access in browser and Windows privacy settings, and verify internet/transcription access beforehand.
5. Have a non-sensitive JPG, JPEG, or PNG photo ready for the image scenario.

## Five-minute workflow

### 0:00–0:30 — Introduce the project

- Click **Home**.
- Point out the IntentWeave AI title, course label, three modules, and local metrics.
- Explain: actions are local and approval-gated; optional AI calls depend on provider credentials and connectivity.

### 0:30–1:10 — Scenario 1: text command

- Click **Demo Mode**, then **Use this prompt** under “1 · Text command.”
- In **AI Assistant**, submit “Explain artificial intelligence in simple words.”
- If an AI key is not configured, show the honest offline-mode response rather than implying it generated an AI explanation.
- Expand **View 3-module processing trace** to show the input, rule-based intent, and response path.

### 1:10–1:45 — Scenario 2: contextual follow-up

- Return to **Demo Mode** and select “2 · Context follow-up.”
- Submit “Explain its applications.”
- With an AI provider configured, the prior messages are sent as conversation context. Without it, the app clearly indicates that open-ended follow-up generation needs a provider.
- Open **Context Memory** to show the persisted turns.

### 1:45–2:30 — Scenario 3: voice input

- From **Demo Mode**, click **Open multimodal input** for “3 · Voice input.”
- Record: “Create a task to submit my assignment tomorrow.”
- Submit the recording. The recognized transcript is displayed and routed through the same command classifier.
- If transcription is unavailable, explain the microphone/network/API limitation and use text input; do not claim a transcript was produced.

### 2:30–3:10 — Scenario 4: image input

- Select “4 · Image input” in **Demo Mode**.
- Upload the prepared photo or capture one with the camera.
- Show the preview, pixel dimensions, brightness, approximate color tendency, and edge density.
- Ask “What is in this image?” With the optional vision provider configured, show its response. Without it, explain that OpenCV measurements are not object recognition.

### 3:10–4:20 — Scenario 5: verified action

- From **Demo Mode**, choose **Use this prompt** under “5 · Verified action.”
- Submit “Create a task called Prepare capstone presentation.”
- Review the proposed task. Point out that nothing has been changed yet.
- Click **Confirm** to save, or **Cancel** to demonstrate the no-change path.
- Open **Action Center** to show the task and status history.

### 4:20–5:00 — Scenario 6: analytics and wrap-up

- Click **Analytics**.
- Show command totals, modality/intent charts, recent interactions, and action status activity.
- Explain local functionality versus optional network-backed AI and name the key limitations: one local user, rule-limited offline intent reasoning, no object recognition from OpenCV alone, and no arbitrary external actions.

## What is local versus optional

| Capability | Execution |
| --- | --- |
| UI, SQLite history, rule-based intents, safe arithmetic, tasks/notes, approvals, action log, analytics | Local |
| Image dimensions, brightness, approximate color, edge density | Local OpenCV; not semantic recognition |
| Optional AI chat and image questions | Configured API key, reachable provider, model/account access |
| Speech transcription | Configured transcription API, or internet-backed Google recognition without that key |
| Speak response button | Browser Web Speech API; browser support required |

No sample responses are fabricated by Demo Mode. Every prompt enters the ordinary assistant processing flow, and saving data always requires confirmation.
