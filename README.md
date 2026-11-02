# Nexo

Asistente accesible de escritorio para Windows. Permite hablar o escribir peticiones, consultar la pantalla y ejecutar un conjunto limitado de acciones con confirmación local. Puedes elegir Gemini o GPT-6 Luna en la interfaz.

## Instalar

Descarga `Nexo-Setup-1.0.0.exe` desde [Releases](https://github.com/edre1/Nexo/releases) y ejecútalo en Windows 10 u 11 de 64 bits. El instalador no requiere Python. En el menú Inicio, abre **Configurar claves API** y añade una clave de Gemini u OpenAI. Las claves se guardan en tu perfil de Windows y no se incluyen en el repositorio ni en el instalador.

## Versión de pruebas

El código de la versión con Python está en [`accessible_ai_assistant`](accessible_ai_assistant). Consulta sus instrucciones para ejecutar `iniciar.bat` y probar cambios. El código del instalador está en [`produccion`](produccion).

## Actualizaciones

Nexo comprueba la última publicación de este repositorio cuando pulsas **Buscar actualizaciones**. Si hay una versión nueva, abre su página para descargar el instalador. El instalador conserva las claves y registros en `%APPDATA%\AsistenteAccesibleWindows`.

Para publicar una versión nueva, actualiza el número en `accessible_ai_assistant/config/release.json` y `produccion/installer.iss`, confirma los cambios y crea un tag `vX.Y.Z`. La acción de GitHub compila el instalador y lo adjunta a una publicación.
