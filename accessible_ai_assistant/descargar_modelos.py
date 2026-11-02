"""Optional first-time model setup; no credentials are required."""
from speech.local_models import download_models

if __name__ == "__main__":
    download_models(print)
    print("Piper listo para usar.")
