# Prueba independiente de Whisper base

Haz doble clic en **iniciar_prueba.bat**. Usa Python 3.12 o 3.13 en Windows; si ya probaste Nexo, aprovecha sus componentes y su modelo descargado. En otra computadora instala solo Whisper y el micrófono, sin necesitar Nexo ni claves API. La primera instalación y descarga requieren internet.

1. Si no tienes el modelo, pulsa **Descargar modelo**.
2. Pulsa **Grabar** o **F2**. Espera el aviso **Habla ahora** y el sonido antes de empezar a hablar.
3. Pulsa **F2** otra vez para terminar; también termina al alcanzar el máximo elegido. No corta por silencio.
4. Revisa la transcripción y los segundos que tardó en procesarla. Puedes abrir una grabación con **F3** y enfocar los resultados con **F6**.

La grabación se mantiene en memoria y no se guarda en disco. No ejecuta ninguna orden: si dices «abre la calculadora», solo escribe esas palabras. La transcripción usa CPU, INT8, cuatro hilos, idioma español y los mismos ajustes que la versión de pruebas de Nexo. No envía el audio a una API.

En pruebas de micrófono el modelo se carga antes de grabar para que el aviso sea preciso. En pruebas con archivo se informa la carga inicial por separado; repite la misma prueba para comparar con el modelo ya cargado. La primera carga tarda más. `transcripcion_segundos` mide la espera después de terminar el audio; `audio_segundos` es la duración del audio.

Para probar sin interfaz desde consola: `python prueba_whisper.py --archivo grabacion.wav`.
