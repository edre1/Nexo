$ErrorActionPreference = 'Stop'
$project = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\accessible_ai_assistant')).Path
$python = if ($env:NEXO_BUILD_PYTHON) { $env:NEXO_BUILD_PYTHON } else { Join-Path $project '.venv\Scripts\python.exe' }
$icon = Join-Path $project 'assets\nexo.ico'
$candidates = @(
    (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'),
    'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
    'C:\Program Files\Inno Setup 6\ISCC.exe'
)
$iscc = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not (Test-Path -LiteralPath $python)) { throw 'Primero abre iniciar.bat en la carpeta de pruebas.' }
if (-not $iscc) { throw 'Falta Inno Setup 6.' }
Push-Location $project
try {
    & $python -m PyInstaller --noconfirm --clean --onedir --windowed --name Nexo --icon $icon --collect-data piper --distpath (Join-Path $PSScriptRoot 'dist') --workpath (Join-Path $PSScriptRoot 'build') --specpath $PSScriptRoot --add-data "$icon;assets" --add-data "$(Join-Path $project 'config/config.json');config" --add-data "$(Join-Path $project 'config/release.json');config" main.py
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el programa.' }
    if (-not (Test-Path (Join-Path $PSScriptRoot 'dist/Nexo/_internal/piper/espeak-ng-data/phondata'))) {
        throw 'El ejecutable no contiene los datos de pronunciación de Piper.'
    }
    & $python -m PyInstaller --noconfirm --clean --onefile --windowed --name ConfigurarClaves --icon $icon --distpath (Join-Path $PSScriptRoot 'dist') --workpath (Join-Path $PSScriptRoot 'build') --specpath $PSScriptRoot configurar_clave.py
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el configurador de claves.' }
} finally { Pop-Location }
& $iscc (Join-Path $PSScriptRoot 'installer.iss')
if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el instalador.' }
