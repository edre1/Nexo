"""Check reachability without sending audio, screenshots or API credentials."""
import socket


def internet_available() -> bool:
    for host in ("generativelanguage.googleapis.com", "api.openai.com"):
        try:
            with socket.create_connection((host, 443), timeout=2):
                return True
        except OSError:
            continue
    return False
