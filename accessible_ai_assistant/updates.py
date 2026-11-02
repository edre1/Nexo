"""Read-only update check against one configured GitHub Releases repository."""
import json
from urllib.request import Request, urlopen
from config.paths import RESOURCE_ROOT


def release_settings() -> dict:
    return json.loads((RESOURCE_ROOT / "config" / "release.json").read_text(encoding="utf-8"))


def check_latest() -> tuple[str, str] | None:
    settings = release_settings()
    repo = settings["github_repository"].strip()
    if not repo or len(repo.split("/")) != 2:
        raise ValueError("Todavía no se configuró el repositorio de GitHub para las actualizaciones.")
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    request = Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "AsistenteAccesibleWindows"})
    with urlopen(request, timeout=10) as response:
        release = json.load(response)
    current = tuple(int(part) for part in settings["version"].lstrip("v").split("."))
    latest = tuple(int(part) for part in release["tag_name"].lstrip("v").split("."))
    if latest <= current:
        return None
    page = release["html_url"]
    if not page.startswith(f"https://github.com/{repo}/releases/"):
        raise ValueError("La dirección de la actualización no es válida.")
    return release["tag_name"], page
