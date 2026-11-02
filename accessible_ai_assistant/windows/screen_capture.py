"""One screenshot only when the user explicitly requests a screen description."""
from io import BytesIO
from PIL import Image
import mss


def capture_screen() -> bytes:
    try:
        with mss.mss() as screen:
            raw = screen.grab(screen.monitors[0])
            image = Image.frombytes("RGB", raw.size, raw.rgb)
            image.thumbnail((1600, 1000))
            output = BytesIO()
            image.save(output, format="PNG")
            return output.getvalue()
    except Exception as exc:
        raise RuntimeError("No pude capturar la pantalla.") from exc
