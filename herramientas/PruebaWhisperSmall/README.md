# Comparación de Whisper small y Gemini

Haz doble clic en **iniciar_prueba.bat**. Puedes grabar con **F2**, detener con **F2**, abrir audio con **F3** y enfocar los resultados con **F6**.

La casilla **Comparar también con Gemini** activa el modelo que usaba Nexo al principio: `gemini-3.5-flash-lite`, con la misma instrucción de transcripción. Whisper small sigue trabajando en CPU e INT8. Cada modelo recibe exactamente el mismo audio WAV. Las peticiones a Gemini necesitan internet y están sujetas a los límites y condiciones de tu cuenta. Desmarca la casilla para mantener el audio solo en la computadora.

El campo de clave está oculto y no se guarda. En la carpeta de pruebas entregada se puede reutilizar la clave de la copia de Nexo que está al lado; también puedes pegarla en el campo o usar la variable de entorno `GEMINI_API_KEY`. No se incluyen claves en el ZIP.

Los resultados muestran el texto y el tiempo de cada modelo. La carga inicial de Whisper se informa aparte; en pruebas de micrófono se carga antes de grabar. El tiempo de Gemini incluye la petición por internet. Los modelos se ejecutan uno después del otro y se miden por separado. Si uno falla, se conserva el resultado del otro. Para comparar precisión, di una frase conocida y revisa cuál reproduce mejor sus palabras; esta prueba no asigna una puntuación automática de precisión.

No se guardan las grabaciones del micrófono ni se ejecutan las órdenes que pronuncies. La primera instalación y la descarga de Whisper requieren internet; si ya probaste Nexo, aprovecha sus componentes. El modelo small se descarga por separado y conserva base en la computadora. En otra computadora necesita Python 3.12 o 3.13.

Esta prueba utiliza ahora **Whisper small multilingüe**, con CPU e INT8. La prueba independiente cambió de modelo; la aplicación principal Nexo conserva su configuración hasta que decidamos integrar el resultado de estas pruebas. Small consume más recursos y puede tardar más que base: revisa los tiempos mientras también tienes abiertas tus aplicaciones habituales.

Desde consola: `python prueba_whisper.py --archivo grabacion.wav --comparar`. Sin `--comparar`, transcribe solo con Whisper.
