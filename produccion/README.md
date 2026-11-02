# Versión instalable

`Nexo-Setup-1.0.0.exe` instala la aplicación para el usuario actual de Windows. No requiere Python en la computadora de destino. Las claves y registros se guardan en `%APPDATA%\AsistenteAccesibleWindows`, fuera de la carpeta de instalación, para conservarlos al actualizar.

El menú Inicio incluye **Configurar claves API**. Después de guardar una clave, cierra y vuelve a abrir el asistente. La carpeta `outputs/AsistenteAccesibleWindows` sigue siendo la versión de pruebas con Python.

## Actualizaciones desde GitHub

El botón **Buscar actualizaciones** consulta la última publicación de `edre1/Nexo` y abre su página de descarga cuando hay una versión más reciente. Publica el instalador en una publicación de GitHub cuyo tag sea `v1.0.0` o superior. Usa el mismo `AppId` de `installer.iss` en versiones futuras; Inno Setup actualizará la instalación existente y conservará las claves en AppData.

El repositorio está configurado en `config/release.json`. La versión 1.0.0 se publicará en GitHub Releases.
