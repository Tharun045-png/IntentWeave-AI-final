# IntentWeave AI — Testing record

## Test environment

- Windows 11 / PowerShell
- Python 3.12.10 in the project `.venv`
- Streamlit 1.67.0, OpenCV 5.1.0, NumPy 2.5.5
- Tests run with `python -m pytest -q`

## Automated cases

| Coverage | Test |
| --- | --- |
| Intent parsing, including task title normalization | `test_intent_recognition` |
| Safe arithmetic and rejection of calls/unsafe expressions | `test_safe_arithmetic` |
| Proposal has no side effect, approval performs action, per-conversation separation | `test_confirmation_required_and_data_is_separated` |
| Follow-up resolution from recent module context | `test_contextual_followup` |
| Database export and ordinal module parsing | `test_ordinal_modules_and_database_export` |
| Persistent modality/intent metrics and pending-to-completed approval transitions | `test_database_analytics_tracks_input_and_current_approval_state` |
| Migration of an existing action log schema | `test_existing_action_log_schema_migrates_request_id` |
| OpenCV dimensions/brightness/report generation | `test_image_analysis_reports_measured_properties` |
| Invalid image rejection | `test_invalid_image_fails_cleanly` |

## Results

- Initial baseline test attempt: **blocked** because `pytest` was not installed in the existing virtual environment.
- Installed the missing `pytest` test runner into `.venv`; no project runtime dependency was added for it.
- The first post-change run identified an analytics ordering defect in pending approval aggregation. It was corrected to use the latest logged status per request.
- Live UI checks exposed broken preinstalled Windows binary wheels for `rpds-py`, pandas, PyArrow, and Pillow. Reinstalled those packages in the project `.venv`; the dependencies required by Streamlit charts, OpenCV, and image preview now import successfully. Explicit chart dependencies are listed in `requirements.txt`.
- Final automated result: **9 passed** with `python -m pytest -q`.
- Python syntax check: **passed** with `python -m compileall -q app.py engine.py media.py database.py tests`.
- Live Streamlit health endpoint: **passed** at `/_stcore/health` using an isolated temporary database.
- Browser smoke checks: **passed** for Home, Demo Mode, About Project, Analytics charts with saved counts, calculator chat, confirmed task creation, and uploaded/processed PNG analysis with measured OpenCV properties.
- Voice recording/transcription and provider-backed chat/vision were not exercised because they require browser microphone permission and/or external credentials/network access; those limitations are described in the app.
