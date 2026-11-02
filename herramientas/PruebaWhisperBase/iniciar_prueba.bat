@echo off
cd /d "%~dp0"
set "WHISPER_ENV=%LOCALAPPDATA%\PruebaWhisperBase\entorno"
if exist "%LOCALAPPDATA%\Nexo\entorno-pruebas\Scripts\python.exe" (
  "%LOCALAPPDATA%\Nexo\entorno-pruebas\Scripts\python.exe" prueba_whisper.py
  if errorlevel 1 pause
  exit /b
)
if not exist "%WHISPER_ENV%\Scripts\python.exe" (
  py -3.13 -m venv "%WHISPER_ENV%"
  if errorlevel 1 py -3.12 -m venv "%WHISPER_ENV%"
)
if not exist "%WHISPER_ENV%\requirements.installed" goto instalar
fc /b requirements.txt "%WHISPER_ENV%\requirements.installed" >nul
if errorlevel 1 goto instalar
goto ejecutar
:instalar
"%WHISPER_ENV%\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
  pause
  exit /b 1
)
copy /y requirements.txt "%WHISPER_ENV%\requirements.installed" >nul
:ejecutar
"%WHISPER_ENV%\Scripts\python.exe" prueba_whisper.py
if errorlevel 1 pause
