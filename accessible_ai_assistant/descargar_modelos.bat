@echo off
cd /d "%~dp0"
set "NEXO_ENV=%LOCALAPPDATA%\Nexo\entorno-pruebas"
if not exist "%NEXO_ENV%\Scripts\python.exe" (
  echo Abre iniciar.bat primero para instalar los componentes.
  pause
  exit /b 1
)
"%NEXO_ENV%\Scripts\python.exe" descargar_modelos.py
pause
