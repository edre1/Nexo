@echo off
cd /d "%~dp0"
set "NEXO_ENV=%LOCALAPPDATA%\Nexo\entorno-pruebas"
if not exist "%NEXO_ENV%\Scripts\python.exe" (
  echo Abre iniciar.bat primero para instalar la aplicacion.
  pause
  exit /b 1
)
"%NEXO_ENV%\Scripts\python.exe" configurar_clave.py
if errorlevel 1 exit /b 1
echo Claves guardadas. Cierra y vuelve a abrir la aplicacion para usarlas.
pause
