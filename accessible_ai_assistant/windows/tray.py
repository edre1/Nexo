"""Notification area controls. Callbacks are queued for the Tk thread."""
from PIL import Image
import pystray

from config.paths import RESOURCE_ROOT


class TrayIcon:
    def __init__(self, events):
        with Image.open(RESOURCE_ROOT / "assets/nexo.ico") as source:
            image = source.copy()
        self.icon = pystray.Icon(
            "Nexo", image, "Nexo",
            menu=pystray.Menu(
                pystray.MenuItem("Abrir Nexo", lambda *_: events.put(("quick_text",)), default=True),
                pystray.MenuItem("Salir de Nexo", lambda *_: events.put(("exit",))),
            ),
        )
        self.icon.run_detached()

    def close(self):
        self.icon.stop()
