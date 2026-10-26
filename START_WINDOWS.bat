@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  start "" "http://127.0.0.1:8765"
  py -3 -m vietgeo.server
) else (
  where python >nul 2>nul
  if %errorlevel%==0 (
    start "" "http://127.0.0.1:8765"
    python -m vietgeo.server
  ) else (
    echo Chua tim thay Python. Cai Python 3.10+ tu https://www.python.org/downloads/
  )
)
pause
