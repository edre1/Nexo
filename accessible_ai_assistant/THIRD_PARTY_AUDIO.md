# Audio local

- Whisper: modelo `base` multilingüe de OpenAI, licencia MIT. https://github.com/openai/whisper
- faster-whisper: implementación mediante CTranslate2, licencia MIT. https://github.com/SYSTRAN/faster-whisper
- Piper: motor `piper-tts`, licencia GPL-3.0-or-later. https://github.com/OHF-Voice/piper1-gpl
- Voz `es_MX-claude-high`: español de México, un hablante, calidad high y frecuencia 22050 Hz. La ficha del modelo declara el conjunto de datos bajo Apache-2.0. https://huggingface.co/rhasspy/piper-voices/tree/main/es/es_MX/claude/high

La descarga conserva la ficha original de la voz como `es_MX-claude-high.MODEL_CARD.txt` junto al modelo. Estos modelos se descargan desde sus repositorios originales; no se incluyen en Git ni en el ZIP de pruebas. La distribución final con Piper deberá acompañarse de los avisos y el código fuente exigidos por sus licencias.
