"""Find and verify the Windows installer published on GitHub Releases."""
from hashlib import sha256
import json
import re
from tempfile import NamedTemporaryFile
from pathlib import Path
from urllib.request import Request, urlopen
from config.paths import DATA_ROOT, RESOURCE_ROOT


def release_settings() -> dict:
    return json.loads((RESOURCE_ROOT / "config" / "release.json").read_text(encoding="utf-8"))


def check_latest(*, download=False):
    settings = release_settings()
    repo = settings["github_repository"].strip()
    if not repo or len(repo.split("/")) != 2:
        raise ValueError("Todavía no se configuró el repositorio de GitHub para las actualizaciones.")
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    request = Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "AsistenteAccesibleWindows"})
    with urlopen(request, timeout=10) as response:
        release = json.load(response)
    current = tuple(int(part) for part in settings["version"].lstrip("v").split("."))
    tag = release["tag_name"]
    if not re.fullmatch(r"v\d+\.\d+\.\d+", tag) or release.get("prerelease") or release.get("draft"):
        return None
    latest = tuple(int(part) for part in tag[1:].split("."))
    if latest <= current:
        return None
    page = release["html_url"]
    if not page.startswith(f"https://github.com/{repo}/releases/"):
        raise ValueError("La dirección de la actualización no es válida.")
    if not download:
        return tag, page
    filename = f"Nexo-Setup-{tag[1:]}.exe"
    url = f"https://github.com/{repo}/releases/download/{tag}/{filename}"
    asset = next((item for item in release["assets"] if item["name"] == filename and item["browser_download_url"] == url), None)
    if asset is None:
        raise ValueError("La versión de GitHub no contiene el instalador esperado.")
    digest = asset.get("digest") or ""
    size = asset["size"]
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest) or not 0 < size <= 200 * 1024 * 1024:
        raise ValueError("GitHub no devolvió datos válidos para verificar el instalador.")
    directory = DATA_ROOT / "updates"
    directory.mkdir(parents=True, exist_ok=True)
    partial = None
    try:
        with NamedTemporaryFile(dir=directory, suffix=".download", delete=False) as file:
            partial = Path(file.name)
            checksum = sha256()
            received = 0
            with urlopen(url, timeout=30) as response:
                while chunk := response.read(256 * 1024):
                    received += len(chunk)
                    if received > size:
                        raise ValueError("El instalador descargado supera el tamaño publicado.")
                    file.write(chunk)
                    checksum.update(chunk)
        if received != size or "sha256:" + checksum.hexdigest() != digest:
            raise ValueError("El instalador descargado no coincide con el publicado en GitHub.")
        installer = directory / "Nexo-Setup.exe"
        partial.replace(installer)
        return tag, installer
    finally:
        if partial is not None:
            partial.unlink(missing_ok=True)
