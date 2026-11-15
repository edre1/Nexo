# Asistente accesible de Windows — primera versión

## Registro y envío de errores por correo

El registro central guarda errores de interfaz, peticiones a la IA, acciones, voz, descargas, atajos y excepciones Python sin capturar de arranque o hilos. Conserva fecha, versión, tipo de error, estado HTTP cuando existe y nombres de módulos/funciones con números de línea. No guarda el mensaje original de las excepciones, argumentos, variables, conversaciones, audio, capturas, claves ni rutas personales. Los errores de validación indican el campo y el tipo de fallo sin conservar su contenido.

Abre el menú superior **Configuración → Reportes de errores**. Indica destinatario, cuenta remitente, servidor SMTP y su contraseña de aplicación. En Gmail utiliza `smtp.gmail.com`, puerto `587` y una contraseña de aplicación permitida por tu cuenta; no se utiliza la contraseña normal de Google. Consulta la ayuda oficial: https://support.google.com/accounts/answer/185833?hl=es

Pulsa **Enviar prueba** para comprobar la cuenta. Para enviar automáticamente, marca **Activar envío automático** y guarda. La aplicación comprueba la cola cada 30 segundos y envía como máximo un resumen por hora, con hasta 20 grupos por correo. Los errores repetidos se agrupan por ventanas de diez minutos y se cuenta cuántas veces ocurrieron. Si el correo falla, conserva los pendientes y reintenta con esperas progresivas; al recuperar internet permite reintentar de nuevo. **Enviar pendientes** permite un envío manual inmediato. Un fallo de conexión después de aceptar el correo puede ocasionar un duplicado.

**Exportar** guarda un JSON técnico para revisarlo o compartirlo manualmente. Los reportes pendientes se conservan hasta que se envíen. Los ya enviados se conservan 90 días y se limpian al registrar nuevos eventos. La cola está en `error_reports/errors.sqlite3` dentro de la carpeta de datos de Nexo. Los cierres forzados por Windows, cortes de energía y fallos nativos que terminan el proceso pueden no producir un reporte Python; no se garantiza registrar todos los fallos posibles del sistema.

La configuración local está en `error_reporting.json`; la contraseña se protege con DPAPI de Windows para el usuario y la computadora actuales. Configura el envío en la laptop donde quedará instalada la aplicación. En la versión instalable estos archivos viven en `%APPDATA%\AsistenteAccesibleWindows`, y se conservan al actualizar. La credencial del correo, su dirección y los reportes no se incluyen en Git ni en el ZIP de pruebas. Al copiar manualmente una carpeta de pruebas, excluye `.env`, `preferences.json`, `error_reporting.json` y `error_reports`.

El envío permanece desactivado hasta configurar una credencial válida y activarlo. Estos cambios aún son de pruebas y no están en el instalador publicado 1.0.0.

## Razonamiento automático de Luna

Nexo elige y envía explícitamente `reasoning.effort` en cada consulta a GPT-6 Luna. Usa **bajo** para órdenes breves como «Abre la calculadora», **medio** para consultas generales y **alto** para análisis, comparación o tareas con varios pasos. La elección usa reglas locales: no añade una consulta extra a la API. Es una estimación del tipo de petición, no una medición exacta de su dificultad; en casos dudosos usa medio.

Para interpretar imágenes o manejar la ventana se utiliza al menos medio. Si el control visual necesita más de cuatro respuestas, sube a alto para los siguientes pasos. Las continuaciones breves como «Sí, hazlo» toman en cuenta el diálogo reciente. La transcripción de voz no utiliza este ajuste.

La interfaz muestra el nivel solicitado y la fase de la tarea; **Alt+R** lo lee en voz alta. Ese indicador muestra el esfuerzo enviado a OpenAI, no el razonamiento interno del modelo. Las confirmaciones y los límites del control visual siguen aplicándose con cualquier nivel. Un nivel alto puede tardar más y consumir más tokens; esta selección no garantiza un ahorro ni una respuesta correcta en todos los casos.

## Control visual de Luna en pruebas

Selecciona **GPT-6 Luna**, activa primero la ventana que quieres manejar y utiliza el atajo de voz. También puedes volver a Nexo y escribir una petición sobre la última ventana activa. Prueba con «Mueve el puntero al centro de la ventana» o «Haz clic en el cuadro de búsqueda y escribe prueba».

Luna usa la herramienta nativa `computer` de OpenAI. Nexo envía una captura de la ventana elegida, valida las acciones devueltas, las ejecuta y devuelve una nueva captura. El ratón usa coordenadas relativas a esa captura sin reducir la imagen. Un círculo magenta en las capturas representa la posición del puntero. No se ejecuta código generado por la IA.

Confirma el inicio de la sesión y luego cada clic, escritura, combinación de teclas o arrastre. **Ctrl+Alt+Escape** detiene la sesión; el botón Detener y Escape también cancelan cuando Nexo tiene el foco. La confirmación de cambios permanece obligatoria en el control visual. El movimiento del puntero, las capturas y el desplazamiento vertical no piden una confirmación adicional.

Esta primera integración controla una ventana de Bloc de notas, Word, Chrome, Edge, VS Code, Explorador o Calculadora. Si cambia el foco a otra aplicación, aparece una ventana distinta o se mueve/redimensiona la ventana, se detiene para evitar usar coordenadas desactualizadas. Para continuar, activa el destino correcto y pide una tarea nueva. Se admiten desplazamientos verticales. Hay límites de 12 respuestas, 40 acciones y 3 minutos por tarea; una petición API en curso puede tardar unos segundos en devolver el control tras cancelar.

Las capturas se envían a OpenAI durante la sesión y cuentan para el uso de la API. Las páginas, documentos y diálogos pueden contener instrucciones engañosas; deben tratarse como información y revisarse antes de aprobar cambios. Las operaciones de envío, compra, instalación y borrado quedan fuera de esta prueba; algunos controles se bloquean según su nombre accesible. La identificación visual puede equivocarse: revisa la acción que confirmas.

Se retiró la antigua acción `move_cursor` del catálogo, de los esquemas y del controlador de Windows. Gemini conserva sus acciones fijas, sin movimiento de cursor. El nuevo control visual se utiliza con Luna y permite manejar tanto el puntero como el teclado.

## Modo avanzado de Luna

Con Luna seleccionado, abre Preferencias con Ctrl+, y marca **Activar modo avanzado de Luna**. Nexo recuerda la opción al reiniciar y solo la aplica con Luna. Ctrl+Alt+Escape detiene la sesión si conservas el atajo predeterminado.

Abre **Configuración → Registro del modo avanzado** para consultar `advanced_activity/actividad.txt`. Registra comandos, acciones visuales, rutas conocidas y resultados. Las copias previas de archivos identificados de hasta 20 MiB quedan en `advanced_activity/copias`. El registro es local y puede contener datos de la tarea. Los efectos indirectos de un comando o clic y los cambios en servicios externos pueden quedar sin detectar y requerir corrección manual.

## Reconocimiento y voz

En Preferencias puedes activar **Escuchar antes de enviar**. Nexo lee la transcripción en voz alta. Pulsa Enter para aceptarla, Escape para cancelar u otra tecla para volver a grabar. El envío automático ocurre tres segundos después de terminar la lectura.

Nexo transcribe con la API del proveedor seleccionado: Gemini o `gpt-transcribe` de OpenAI. Whisper se retiró de la aplicación. Piper conserva la voz local **Claude high en español de México**, con la voz de Windows como alternativa.

La escucha dura como máximo **60 segundos** y termina al detectar **3 segundos consecutivos de silencio**. El aviso **«Habla ahora»** se reproduce después de abrir el micrófono; la grabación descarta ese aviso para que no aparezca en la transcripción.

En Configuración puedes elegir Piper o Windows. El botón **Descargar modelos locales** descarga únicamente la voz de Piper. Los datos de la voz se guardan en `%LOCALAPPDATA%\Nexo\models`. Las consultas y la transcripción necesitan internet; los avisos de voz funcionan localmente.

El arranque de pruebas instala los componentes en `%LOCALAPPDATA%\Nexo\entorno-pruebas` para evitar el límite de rutas largas de Windows. No necesita modificar la configuración del sistema. Estos cambios todavía no se publican en el instalador de producción.

## Interfaz de chat en pruebas

El menú **Configuración** incluye **Estado de Nexo** y **Atajos de teclado**. Al recorrer el chat con Alt y flechas, Nexo interrumpe la lectura anterior. En Preferencias puedes silenciar el recordatorio de teclas de la revisión del dictado.

En Preferencias puedes permitir que Gemini busque en internet. La búsqueda está desactivada por defecto. Gemini puede consultar la pantalla y sus controles. Las acciones de control de Windows se realizan con Luna.

La ventana muestra la conversación en burbujas y anuncia respuestas y errores con la voz de Windows.

- Enter envía el mensaje escrito. Tab y Mayús+Tab recorren los controles.
- Alt+M lleva al campo de mensaje; Alt+H lleva a la conversación; F6 alterna entre ambos.
- Alt+Arriba y Alt+Abajo recorren los mensajes y los leen en voz alta. En la conversación también puedes seleccionar texto y copiar con Ctrl+C.
- Ctrl+, abre Configuración. Selecciona la letra o número que acompañará a Ctrl+Alt para hablar y pulsa Guardar. Si el atajo está ocupado, se anuncia el error y se conserva el anterior.
- Ctrl+Alt+F8 alterna entre Gemini para preguntas sencillas y Luna para peticiones complejas. Puedes cambiar esa combinación en Preferencias (Ctrl+,). Nexo anuncia el cambio en voz alta. Al abrir la aplicación, usa Luna si su clave está configurada.
- El atajo se guarda en `preferences.json`, que es una preferencia local y no se publica.
- Nexo comprueba la conexión al abrir, periódicamente y antes de iniciar una petición. Sin conexión desactiva Escuchar y Enviar, conserva el mensaje escrito y anuncia la desconexión una vez. Al recuperarse la conexión, vuelve a habilitar el envío y lo anuncia.

Estos cambios corresponden a la versión de pruebas. El instalador publicado 1.0.0 no se modifica.

Aplicación de escritorio para pedir por voz o por texto acciones concretas de Windows. Puedes elegir Gemini o GPT-6 Luna en la interfaz para interpretar cada petición. Una política local valida la acción y sus parámetros antes de que el programa toque Windows.

Esta carpeta es la **versión de pruebas con Python**. La versión instalable Nexo para Windows está en `../produccion/Nexo-Setup-1.0.0.exe`.

Los modelos de prueba son `gemini-3.5-flash-lite` y `gpt-6-luna`. La opción de OpenAI usa además `gpt-transcribe` para convertir las peticiones de voz en texto.

## Requisitos

- Windows 10 u 11, Python 3.12 o 3.13 de 64 bits e internet.
- Micrófono predeterminado, salida de audio y una clave válida de Gemini API o OpenAI API.
- NVDA es compatible, pero no obligatorio. La voz predeterminada es Piper; Windows SAPI se conserva como alternativa.

El reconocimiento de voz graba hasta 60 segundos, con corte tras 3 segundos de silencio, y envía el audio a Gemini o a `gpt-transcribe` de OpenAI. La descripción visual envía una captura al proveedor seleccionado cuando se pregunta por la pantalla. Las consultas a la IA dependen de internet y de los límites de cada cuenta. OpenAI API puede generar cargos por uso.

## Instalación y traslado a otra computadora

Desde la versión instalada 1.2.0, Nexo comprueba las actualizaciones al arrancar y después cada hora. Descarga y verifica el instalador de GitHub, espera a que termine la petición activa y se reinicia tras instalarlo. La copia de pruebas se actualiza por separado.

El instalador ofrece **Iniciar Nexo en segundo plano al iniciar sesión en Windows**. Con esa opción marcada, los atajos globales funcionan desde otras aplicaciones sin abrir el chat. Para mostrarlo, abre Nexo desde el menú Inicio o el escritorio. Para ocultarlo de nuevo, usa **Configuración → Ocultar y seguir escuchando el atajo**.

1. Extrae el ZIP o copia esta carpeta a la computadora donde lo usarás.
2. Comprueba que Windows tenga Python 3.12 o 3.13 de 64 bits instalado. En esta computadora ya está instalado.
3. Haz doble clic en `iniciar.bat`.
4. La primera vez, espera mientras instala los componentes; necesita internet. Cuando aparezca «Configurar claves de IA», pega una o ambas claves y pulsa «Guardar claves» o Enter.
5. Para volver a abrirlo después, haz doble clic en `iniciar.bat` otra vez.

Las claves se guardan en `.env` dentro de esta carpeta, pero no están incluidas en el ZIP entregado. Para agregar la clave de OpenAI después, haz doble clic en `configurar_claves.bat`, pégala en **Clave de OpenAI API** y pulsa **Guardar claves**. Deja vacío el campo de Gemini para conservar su clave existente. Cierra y vuelve a abrir la aplicación. También puedes abrir `.env` con Bloc de notas y escribir `OPENAI_API_KEY=tu_clave` en una línea propia. Si copias la carpeta ya configurada a otra persona o computadora, elimina antes `.env`, `.venv` y `logs`. La carpeta no depende de rutas absolutas de la computadora original.

Si prefieres instalar manualmente, abre PowerShell en esta carpeta y ejecuta `py -3.13 -m venv .venv`, luego `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`. Crea `.env` a partir de `.env.example` y ejecuta `.\.venv\Scripts\python.exe main.py`.

## Uso y prueba manual completa

1. Abre la aplicación. El estado mostrará qué claves están configuradas y cuál modelo está activo. Usa la lista **Modelo para la siguiente petición** para elegir Gemini o GPT-6 Luna. Solo podrás elegir un modelo si agregaste su clave.
2. Pulsa `Ctrl+Alt+A`. Se oye «Habla ahora» cuando el micrófono está listo.
3. Di «Abre el Bloc de notas». El modelo seleccionado debe devolver `open_application`; la política admite `notepad`; Windows lo abre y el asistente anuncia el resultado.
4. Con Bloc de notas al frente, pulsa el atajo y di «¿Qué ventana tengo abierta?». Debe leer el título de Bloc de notas.
5. Di «Escribe Hola mundo». Confirma en el diálogo con teclado. Debe escribir exactamente ese texto en la ventana que estaba activa al solicitarlo.
6. Di «Guarda el archivo». Confirma. Si aparece «Guardar como», el asistente lo anuncia; el usuario elige nombre y ubicación con teclado. No se acepta una ruta sugerida por la IA.
7. Con Visual Studio Code abierto, di «¿Qué hay en esta ventana?» o «¿Qué controles hay?». Obtendrá información accesible y, para descripción de pantalla, una captura bajo demanda.
8. Prueba una pregunta concreta como «¿Qué fecha aparece en la pantalla?». El asistente debe responder la fecha, en lugar de enumerar toda la pantalla. La pregunta original se envía junto con la captura al modelo seleccionado.

Para probar sin micrófono, escribe la misma petición en la caja de texto y pulsa Enter. Para cancelar la escucha usa `Ctrl+Alt+Escape` desde cualquier aplicación o el botón «Detener o cancelar». `Escape` cancela cuando la ventana del asistente tiene el foco.

## Acciones permitidas

Lectura y navegación: ventana activa, controles visibles, foco actual, texto seleccionado, descripción de pantalla y enfoque de un control por nombre accesible. Apertura de aplicaciones: Bloc de notas, Chrome, Visual Studio Code, Edge, Explorador y Calculadora, si están instaladas. Volumen: subir, bajar y silenciar.

Con Gemini, los clics fijos se hacen por nombre accesible mediante UI Automation y están limitados a controles de navegación comunes. Con Luna, las peticiones de ratón y teclado se dirigen al control visual descrito arriba.

Acciones que piden confirmación: escribir texto, presionar una tecla de la lista cerrada, activar un control de navegación, guardar y solicitar el cierre de la ventana. Las teclas y nombres de clic permitidos están en `actions/action_registry.py`. El diálogo de confirmación está en la aplicación, no lo decide Gemini.

Están bloqueadas las aplicaciones fuera de la lista, rutas proporcionadas por la IA, comandos de shell, borrado de archivos, instalación, administración, cambios de permisos y otras acciones que no aparezcan en el catálogo. No hay `eval`, ejecución de texto generado, ni acceso directo de Gemini al sistema operativo.

## Accesibilidad y límites actuales

- Todos los controles de la interfaz tienen etiquetas de texto y se alcanzan con Tab. Se puede leer el resultado en la ventana si la voz se superpone a NVDA.
- UI Automation depende de lo que cada programa exponga. Algunos editores y aplicaciones web tienen controles poco descriptivos. El control visual de Luna puede usar coordenadas del ratón dentro de la ventana elegida.
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

Ambos proveedores usan las mismas instrucciones de acciones y la misma validación local. El selector cambia la interpretación y la descripción visual para la siguiente petición. La transcripción también cambia con el proveedor seleccionado.

## Pruebas automáticas

`.\.venv\Scripts\python.exe -m unittest discover -s tests -v`

Comprueban validación, bloqueo y el flujo interpretar → seguridad → ejecutar con simuladores. La prueba real de micrófono, Gemini, ventanas y NVDA debe realizarse en una sesión de escritorio de Windows.
