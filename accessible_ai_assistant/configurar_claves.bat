@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Abre iniciar.bat primero para instalar la aplicacion.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" configurar_clave.py
if errorlevel 1 exit /b 1
echo Claves guardadas. Cierra y vuelve a abrir la aplicacion para usarlas.
pause
