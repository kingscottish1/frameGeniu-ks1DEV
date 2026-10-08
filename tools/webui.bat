@echo off
cd /d "%~dp0\.."
if not exist ".venv\Scripts\python.exe" call "%~dp0\..\INSTALL.bat" /silent
".venv\Scripts\python.exe" -m streamlit run webui\streamlit_app.py --server.address 0.0.0.0 --server.port 8501
