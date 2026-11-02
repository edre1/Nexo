@echo off
cd /d "%~dp0"
set "NEXO_ENV=%LOCALAPPDATA%\Nexo\entorno-pruebas"
if not exist "%NEXO_ENV%\Scripts\python.exe" (
  echo Preparando el asistente por primera vez...
  py -3.13 -m venv "%NEXO_ENV%" 2>nul
  if errorlevel 1 py -3.12 -m venv "%NEXO_ENV%" 2>nul
  if not exist "%NEXO_ENV%\Scripts\python.exe" (
    echo Necesitas Python 3.12 o 3.13 de 64 bits. Consulta README.md.
    pause
    exit /b 1
  )
)
if not exist "%NEXO_ENV%\requirements.installed" goto instalar
fc /b requirements.txt "%NEXO_ENV%\requirements.installed" >nul
if errorlevel 1 goto instalar
goto instalado
:instalar
  echo Instalando componentes. Esto puede tardar unos minutos y requiere internet.
  "%NEXO_ENV%\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
  if errorlevel 1 (
    echo No se pudieron instalar los componentes. Revisa la conexion a internet.
    pause
    exit /b 1
  )
  copy /y requirements.txt "%NEXO_ENV%\requirements.installed" >nul
:instalado
if not defined GEMINI_API_KEY if not defined OPENAI_API_KEY if not exist ".env" (
  "%NEXO_ENV%\Scripts\python.exe" configurar_clave.py
  if errorlevel 1 (
    echo Falta configurar una clave API.
    pause
    exit /b 1
  )
)
"%NEXO_ENV%\Scripts\python.exe" main.py
if errorlevel 1 pause
