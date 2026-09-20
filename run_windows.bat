@echo off
title Network Monitor Web Dashboard
where py >nul 2>nul
if %errorlevel%==0 (
    py -m pip install -r requirements.txt
    py app.py
) else (
    python -m pip install -r requirements.txt
    python app.py
)
pause
