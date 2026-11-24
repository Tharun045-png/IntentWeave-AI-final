@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Creating Python environment...
  py -3 -m venv .venv
  if errorlevel 1 (
    echo Python 3 was not found. Install Python 3.10 or newer and enable the Python launcher.
    pause
    exit /b 1
  )
)
set PYTHONUTF8=1
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
  echo Package installation failed. Check Python and internet connection.
  pause
  exit /b 1
)
.venv\Scripts\python.exe -m streamlit run app.py
if errorlevel 1 (
  echo IntentWeave AI stopped with an error. Review the terminal output above.
  pause
  exit /b 1
)
pause
