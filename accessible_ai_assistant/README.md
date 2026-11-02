# Asistente accesible de Windows — primera versión

Aplicación de escritorio para pedir por voz o por texto acciones concretas de Windows. Puedes elegir Gemini o GPT-6 Luna en la interfaz para interpretar cada petición. Una política local valida la acción y sus parámetros antes de que el programa toque Windows.

Esta carpeta es la **versión de pruebas con Python**. La versión instalable Nexo para Windows está en `../produccion/Nexo-Setup-1.0.0.exe`.

Los modelos de prueba son `gemini-3.5-flash-lite` y `gpt-6-luna`. La opción de OpenAI usa además `gpt-transcribe` para convertir las peticiones de voz en texto.

## Requisitos

- Windows 10 u 11, Python 3.12 o 3.13 de 64 bits e internet.
- Micrófono predeterminado, salida de audio y una clave válida de Gemini API o OpenAI API.
- NVDA es compatible, pero no obligatorio. La voz del asistente usa SAPI de Windows.

El reconocimiento de voz graba localmente un fragmento de hasta 10 segundos y lo envía al proveedor seleccionado: Gemini o `gpt-transcribe` de OpenAI. La descripción visual envía una captura al proveedor seleccionado **solo** cuando se solicita explícitamente describir la pantalla. Estas funciones dependen de internet y de los límites de cada cuenta. OpenAI API puede generar cargos por uso.

## Instalación y traslado a otra computadora

1. Extrae el ZIP o copia esta carpeta a la computadora donde lo usarás.
2. Comprueba que Windows tenga Python 3.12 o 3.13 de 64 bits instalado. En esta computadora ya está instalado.
3. Haz doble clic en `iniciar.bat`.
4. La primera vez, espera mientras instala los componentes; necesita internet. Cuando aparezca «Configurar claves de IA», pega una o ambas claves y pulsa «Guardar claves» o Enter.
5. Para volver a abrirlo después, haz doble clic en `iniciar.bat` otra vez.

Las claves se guardan en `.env` dentro de esta carpeta, pero no están incluidas en el ZIP entregado. Para agregar la clave de OpenAI después, haz doble clic en `configurar_claves.bat`, pégala en **Clave de OpenAI API** y pulsa **Guardar claves**. Deja vacío el campo de Gemini para conservar su clave existente. Cierra y vuelve a abrir la aplicación. También puedes abrir `.env` con Bloc de notas y escribir `OPENAI_API_KEY=tu_clave` en una línea propia. Si copias la carpeta ya configurada a otra persona o computadora, elimina antes `.env`, `.venv` y `logs`. La carpeta no depende de rutas absolutas de la computadora original.

Si prefieres instalar manualmente, abre PowerShell en esta carpeta y ejecuta `py -3.13 -m venv .venv`, luego `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`. Crea `.env` a partir de `.env.example` y ejecuta `.\.venv\Scripts\python.exe main.py`.

## Uso y prueba manual completa

1. Abre la aplicación. El estado mostrará qué claves están configuradas y cuál modelo está activo. Usa la lista **Modelo para la siguiente petición** para elegir Gemini o GPT-6 Luna. Solo podrás elegir un modelo si agregaste su clave.
2. Pulsa `Ctrl+Alt+A`. Se oye «Asistente listo». Habla cuando indique «Escuchando».
3. Di «Abre el Bloc de notas». El modelo seleccionado debe devolver `open_application`; la política admite `notepad`; Windows lo abre y el asistente anuncia el resultado.
4. Con Bloc de notas al frente, pulsa el atajo y di «¿Qué ventana tengo abierta?». Debe leer el título de Bloc de notas.
5. Di «Escribe Hola mundo». Confirma en el diálogo con teclado. Debe escribir exactamente ese texto en la ventana que estaba activa al solicitarlo.
6. Di «Guarda el archivo». Confirma. Si aparece «Guardar como», el asistente lo anuncia; el usuario elige nombre y ubicación con teclado. No se acepta una ruta sugerida por la IA.
7. Con Visual Studio Code abierto, di «¿Qué hay en esta ventana?» o «¿Qué controles hay?». Obtendrá información accesible y, para descripción de pantalla, una captura bajo demanda.
8. Prueba una pregunta concreta como «¿Qué fecha aparece en la pantalla?». El asistente debe responder la fecha, en lugar de enumerar toda la pantalla. La pregunta original se envía junto con la captura al modelo seleccionado.

Para probar sin micrófono, escribe la misma petición en la caja de texto y pulsa Enter. Para cancelar la escucha usa `Ctrl+Alt+Escape` desde cualquier aplicación o el botón «Detener o cancelar». `Escape` cancela cuando la ventana del asistente tiene el foco.

## Acciones permitidas

Lectura y navegación: ventana activa, controles visibles, foco actual, texto seleccionado, descripción de pantalla y enfoque de un control por nombre accesible. Apertura de aplicaciones: Bloc de notas, Chrome, Visual Studio Code, Edge, Explorador y Calculadora, si están instaladas. Volumen: subir, bajar y silenciar.

También puedes decir «Mueve el cursor tres posiciones a la izquierda», «Ve al inicio del documento» o «Haz clic en Archivo». El movimiento usa teclas de navegación, hasta 20 pasos por petición. Los clics se hacen por nombre accesible mediante UI Automation y están limitados a controles de navegación comunes. No hay clics por coordenadas ni clics genéricos en botones como «Eliminar», «Enviar» o «Aceptar». Si necesitas otro control, se debe agregar como acción explícita con su regla de seguridad.

Acciones que piden confirmación: escribir texto, presionar una tecla de la lista cerrada, activar un control de navegación, guardar y solicitar el cierre de la ventana. Las teclas y nombres de clic permitidos están en `actions/action_registry.py`. El diálogo de confirmación está en la aplicación, no lo decide Gemini.

Están bloqueadas las aplicaciones fuera de la lista, rutas proporcionadas por la IA, comandos de shell, borrado de archivos, instalación, administración, cambios de permisos y otras acciones que no aparezcan en el catálogo. No hay `eval`, ejecución de texto generado, ni acceso directo de Gemini al sistema operativo.

## Accesibilidad y límites actuales

- Todos los controles de la interfaz tienen etiquetas de texto y se alcanzan con Tab. Se puede leer el resultado en la ventana si la voz se superpone a NVDA.
- UI Automation depende de lo que cada programa exponga. Algunos editores y aplicaciones web tienen controles poco descriptivos. Esta versión no usa coordenadas del ratón.
- Un atajo global puede estar ocupado por otra aplicación; el estado lo indica. Se puede cambiar en `config/config.json` a otra combinación `Ctrl+Alt+tecla`.
- El modo de aprendizaje está activo: las solicitudes educativas de HTML, CSS y JavaScript deben recibir una explicación antes de escribir. La confirmación local se mantiene para cualquier escritura.
- La grabación finaliza tras silencio o al máximo configurado. En habitaciones ruidosas puede no cortar bien. El umbral del micrófono es fijo en esta versión.
- No se verifica de forma infalible que un programa abrió su ventana o guardó el archivo; el asistente comunica cuando solo se envió la orden o se abrió un diálogo. La prueba final debe observarse con NVDA o en pantalla.
- No se incluye instalador ni arranque automático. Se ejecuta con Python desde esta carpeta.

## Configuración y privacidad

`config/config.json` contiene el proveedor inicial, el modelo de Gemini, atajos, idioma, modo de aprendizaje y opciones de seguridad. OpenAI usa `gpt-6-luna`. Las claves van en `.env` o en las variables de entorno `GEMINI_API_KEY` y `OPENAI_API_KEY`. `.env.example` nunca contiene claves reales. La selección en la interfaz dura hasta cerrar la aplicación; al abrirla de nuevo se usa el proveedor inicial de `config/config.json` si tiene clave, o el que sí esté configurado.

El archivo `logs/assistant.log` guarda fechas, acciones y errores por tipo. Omite el contenido de dictado que pudiera contener contraseñas, código o mensajes. No guarda audio, capturas ni claves. Puede borrar la carpeta `logs` antes de trasladar el programa.

Para mantener la protección, deja `require_confirmation_for_sensitive_actions` en `true`. Desactivarlo en configuración elimina los diálogos de confirmación para esas acciones.

## Arquitectura y ampliación

- `ai/base_provider.py` define `AIProvider`; `ai/gemini_provider.py` y `ai/openai_provider.py` implementan los dos proveedores.
- `speech/recognizer.py` separa la captura y transcripción; `speech/output.py` habla mediante SAPI.
- `actions/action_models.py` valida la respuesta; `security/security_manager.py` es el único punto de decisión; `actions/action_executor.py` despacha a operaciones fijas.
- `windows/ui_automation.py` consulta controles; `windows/screen_capture.py` captura bajo demanda; `windows/windows_controller.py` contiene las operaciones de Windows.
- `ui/main_window.py` muestra el estado, confirmaciones y resultado.

Ambos proveedores usan las mismas instrucciones de acciones y la misma validación local. El selector cambia la interpretación, la transcripción y la descripción visual para la siguiente petición.

## Pruebas automáticas

`.\.venv\Scripts\python.exe -m unittest discover -s tests -v`

Comprueban validación, bloqueo y el flujo interpretar → seguridad → ejecutar con simuladores. La prueba real de micrófono, Gemini, ventanas y NVDA debe realizarse en una sesión de escritorio de Windows.
