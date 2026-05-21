@echo off
chcp 65001 >nul
echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║          🚀 ПРОГРЕССОР — Запуск...                      ║
echo ╚══════════════════════════════════════════════════════════╝
echo.

:: Запуск бэкенда в фоне
start "Progressor Backend" cmd /k "cd /d %~dp0backend && python app.py"

:: Ждём 3 секунды пока бэкенд запустится
echo.
echo ⏳ Ожидание запуска бэкенда...
timeout /t 3 /nobreak >nul

:: Запуск фронтенда
echo.
echo 🌐 Запуск фронтенда на http://localhost:8000
echo.
start "" http://localhost:8000
cd /d %~dp0
python -m http.server 8000

pause