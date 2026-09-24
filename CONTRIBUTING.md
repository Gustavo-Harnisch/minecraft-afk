# Contribuir a Minecraft AFK

Gracias por dedicar tiempo a mejorar Minecraft AFK. Las contribuciones pueden abarcar código, traducciones, pruebas, documentación o informes de errores reproducibles. El objetivo es mantener una aplicación comprensible y fácil de usar, con un comportamiento predecible al iniciar, calibrar y detener las granjas. Esta guía describe el flujo de trabajo y las verificaciones que ayudan a revisar cada cambio con suficiente contexto.

## Tabla de contenidos

Utiliza este índice para ir directamente al tema que necesitas. Si es tu primera contribución, comienza por la preparación del entorno y la estructura del proyecto; si vas a trabajar con traducciones, revisa también cómo editar los textos, registrar un idioma y comprobar el resultado.

| Tema | Qué encontrarás |
| --- | --- |
| [Formas de colaborar](#formas-de-colaborar) | Ideas para aportar código, traducciones, documentación o informes reproducibles. |
| [Proponer un cambio o informar de un problema](#proponer-un-cambio-o-informar-de-un-problema) | Dónde abrir una incidencia y qué información incluir. |
| [Preparar el entorno](#preparar-el-entorno) | Dependencias, ramas de trabajo e inicio de la aplicación. |
| [Estructura del proyecto](#estructura-del-proyecto) | Carpetas, archivos principales y responsabilidades de cada componente. |
| [Desarrollar un cambio](#desarrollar-un-cambio) | Criterios para modificar la interfaz, los cálculos y las automatizaciones. |
| [Cambiar el idioma de la aplicación](#cambiar-el-idioma-de-la-aplicación) | Selector de idioma, persistencia y pruebas desde la terminal. |
| [Cambiar un texto o corregir una traducción](#cambiar-un-texto-o-corregir-una-traducción) | Diferencia entre modificar una traducción y cambiar el mensaje original. |
| [Contribuir con un idioma nuevo](#contribuir-con-un-idioma-nuevo) | Creación del catálogo y registro del idioma en la aplicación y sus pruebas. |
| [Mantener los catálogos de traducción](#mantener-los-catálogos-de-traducción) | Uso de gettext, variables, extracción y compilación de mensajes. |
| [Verificar los cambios](#verificar-los-cambios) | Pruebas automáticas, revisión visual y comprobaciones según el tipo de cambio. |
| [Actualizar documentación e imágenes](#actualizar-documentación-e-imágenes) | Redacción, enlaces, ejemplos y banner del README. |
| [Resolver problemas frecuentes](#resolver-problemas-frecuentes) | Traducciones que no aparecen, catálogos incompletos y problemas con GTK. |
| [Enviar la contribución](#enviar-la-contribución) | Revisión del diff, commits, publicación de la rama y pull request. |
| [Participar en la revisión y respetar la licencia](#participar-en-la-revisión-y-respetar-la-licencia) | Cómo responder a observaciones y conservar las atribuciones. |

## Formas de colaborar

Puedes empezar por una mejora pequeña y concreta: aclarar una instrucción, corregir una traducción, reproducir una incidencia o añadir una prueba para un fallo conocido. También son útiles las revisiones de accesibilidad, la detección de textos que quedan cortados y las propuestas para presentar mejor la información de durabilidad. Describe siempre qué problema resuelve tu aportación y en qué situación se puede observar la mejora.

Si quieres trabajar con idiomas, puedes revisar los mensajes de español e inglés o preparar un catálogo para otro idioma que conozcas. La revisión debe considerar el significado de cada mensaje dentro de la aplicación, la terminología de Minecraft y los valores que se insertan en el texto. Una traducción automática puede servir como borrador, pero necesita revisión lingüística y una comprobación en la interfaz antes de enviarla.

## Proponer un cambio o informar de un problema

Antes de comenzar, revisa las [incidencias](https://github.com/Gustavo-Harnisch/minecraft-afk/issues) y las [pull requests](https://github.com/Gustavo-Harnisch/minecraft-afk/pulls) existentes para comprobar si alguien está trabajando en el mismo asunto. Una corrección pequeña o una mejora de redacción puede proponerse directamente. Si tu idea modifica el comportamiento de las granjas, la forma de calcular tiempos o la estructura de la aplicación, explicar primero el problema y el resultado esperado en una incidencia facilita acordar el alcance y detectar dependencias.

Un informe de error debe indicar qué intentabas hacer, qué ocurrió y qué esperabas que ocurriera. Añade los pasos para reproducirlo, la distribución de Linux, el tipo de sesión gráfica y la configuración de la granja relevante. Cuando corresponda, incluye la versión de Python, la versión de Minecraft y los mensajes de la pestaña Logs. Si compartes archivos de configuración o registros, elimina antes los datos personales que no sean necesarios para comprender el fallo.

## Preparar el entorno

Parte de un fork del repositorio o de una copia sobre la que tengas permisos de escritura y crea una rama con un nombre que describa el cambio, por ejemplo `fix/calibration-timer` o `docs/installation`. Trabaja desde la raíz del proyecto con Python 3.10 o posterior. En Linux Mint, Ubuntu o Debian, los paquetes del sistema proporcionan GTK3, sus enlaces de Python y las herramientas necesarias; gettext se utiliza para extraer, compilar y comprobar las traducciones.

```bash
sudo apt update
sudo apt install git python3 python3-gi gir1.2-gtk-3.0 xdotool gettext
git switch -c fix/calibration-timer
/usr/bin/python3 main.py
```

Usar `/usr/bin/python3` permite acceder a los enlaces GTK instalados mediante `apt`. Si prefieres un entorno virtual, configúralo para que pueda importar `gi` desde los paquetes del sistema. Las comprobaciones de lógica y catálogos se pueden ejecutar sin una ventana abierta; las pruebas de la interfaz requieren una pantalla disponible. Para comprobar manualmente las acciones de `xdotool`, utiliza una sesión X11.

## Estructura del proyecto

`main.py` inicia la aplicación y `minecraft_afk/window.py` construye la interfaz y actualiza el estado visible. Los cálculos de minado y calibración viven en `minecraft_afk/mining.py`, la persistencia en `minecraft_afk/settings.py` y la construcción y ejecución de comandos en `minecraft_afk/scripts.py`. El módulo `minecraft_afk/config.py` centraliza las rutas y `minecraft_afk/i18n.py` carga los catálogos de idioma. Esta distribución permite revisar la lógica de cálculo o la configuración sin depender de los controles gráficos.

Los scripts de `scripts/` realizan las operaciones de ataque, minado, calibración y parada. Sus mensajes se traducen mediante `scripts/i18n.sh` y `scripts/translate.py`, mientras que `scripts/translations.py` gestiona el mantenimiento de los catálogos. El directorio `locale/` contiene la plantilla `.pot`, los archivos editables `.po` y los archivos `.mo` que usa la aplicación. Las pruebas de lógica, scripts e interfaz se encuentran en `tests/`.

```text
minecraft-afk/
├── README.md                   Guía de instalación y uso
├── CONTRIBUTING.md             Guía de contribución
├── LICENSE                     Licencia MIT
├── main.py                     Inicio de la interfaz GTK
├── minecraft-afk.sh            Entrada común para los comandos
├── minecraft_afk/
│   ├── config.py               Rutas de la aplicación
│   ├── i18n.py                 Selección de idioma y carga de catálogos
│   ├── mining.py               Cálculos de minado y calibración
│   ├── scripts.py              Ejecución de scripts desde Python
│   ├── settings.py             Preferencias persistentes
│   └── window.py               Controles, mensajes y estado de la GUI
├── scripts/
│   ├── minecraft-afk.sh        Despacho de comandos y parada general
│   ├── mob-farm.sh             Ataques automáticos
│   ├── stone-farm.sh           Minado, estimaciones y calibración
│   ├── i18n.sh                 Función de mensajes para Bash
│   ├── translate.py            Traducción de mensajes de los scripts
│   └── translations.py         Extracción, compilación y validación
├── locale/
│   ├── minecraft-afk.pot       Plantilla de mensajes extraídos
│   ├── es/LC_MESSAGES/         Catálogos .po y .mo de español
│   └── en/LC_MESSAGES/         Catálogos .po y .mo de inglés
└── tests/
    ├── test_i18n.py            Idiomas, persistencia y comandos
    └── test_gui_i18n.py        Controles y temporizadores GTK
```

Este esquema muestra los archivos principales. Para cambiar un cálculo, comienza por `mining.py`; para modificar un control o un aviso visual, revisa `window.py`; para corregir una traducción existente, busca su entrada en el catálogo `.po` correspondiente. Mantener estas responsabilidades ayuda a que una modificación de redacción no altere los cálculos ni los identificadores que utilizan los scripts.

## Desarrollar un cambio

Mantén cada contribución centrada en un problema o una mejora que se pueda explicar y revisar de forma independiente. Utiliza nombres descriptivos, conserva el estilo del archivo que estás modificando y añade comentarios cuando ayuden a entender una decisión o una limitación. Si incorporas una dependencia, explica qué necesidad cubre y actualiza las instrucciones de instalación. Las modificaciones que cambien una opción, un comando o una interacción también deben actualizar la documentación correspondiente.

Conserva la separación entre la configuración elegida por la persona, los identificadores internos y los textos de la interfaz. Los argumentos de los scripts deben seguir construyéndose como una lista de valores, y las salidas `clave=valor` deben mantener sus nombres y su representación numérica independientemente del idioma. Evita que una condición del programa dependa de una etiqueta traducida: los estados de preparación, minado y calibración deben identificarse con valores estables y traducirse al presentarlos.

Si modificas las automatizaciones, revisa tanto el inicio como las rutas de parada y de error. El clic mantenido debe liberarse cuando corresponde, y los archivos de proceso y estado deben reflejar la ejecución real. Las pruebas automatizadas deben utilizar rutas temporales y sustituir las acciones del ratón cuando simulen una granja. Esto permite verificar cálculos y transiciones sin controlar la sesión gráfica de quien ejecuta las pruebas.

## Cambiar el idioma de la aplicación

Abre **Ajustes → Idioma**, elige **Español**, **English** o **Automático (idioma del sistema)** y cierra y vuelve a abrir la aplicación. Cuando la interfaz está en inglés, encontrarás la misma opción en **Settings → Language**. La preferencia se guarda en la clave `language` de `~/.config/minecraft-afk/config.json`, o en el directorio equivalente si has definido `XDG_CONFIG_HOME`. El cambio queda pendiente hasta el siguiente inicio; los mensajes de los scripts conservan el idioma activo de la ventana durante la sesión actual.

El modo automático consulta `LANGUAGE`, `LC_ALL`, `LC_MESSAGES` y `LANG`, en ese orden, y reconoce variantes regionales de los idiomas registrados. Cuando no encuentra un idioma compatible, utiliza español. Una selección explícita en Ajustes tiene prioridad sobre el entorno. Para revisar los mensajes de consola sin iniciar una granja, puedes escoger el idioma de una ejecución con `MINECRAFT_AFK_LANGUAGE`:

```bash
MINECRAFT_AFK_LANGUAGE=en ./scripts/mob-farm.sh help
MINECRAFT_AFK_LANGUAGE=es ./scripts/stone-farm.sh help
```

Esa variable afecta a los scripts de consola; no sustituye la preferencia guardada de la GUI. Para probar la detección automática en una ventana independiente de tu configuración habitual, inicia la aplicación con un directorio temporal de ajustes. El siguiente ejemplo abre la interfaz en inglés con la preferencia automática inicial; los cambios que realices se guardarán en ese directorio temporal:

```bash
afk_test_config="$(mktemp -d)"
XDG_CONFIG_HOME="$afk_test_config" LANGUAGE=en /usr/bin/python3 main.py
```

## Cambiar un texto o corregir una traducción

Cada entrada del catálogo contiene un `msgid`, que identifica el mensaje original, y un `msgstr`, que contiene el texto que verá la persona en ese idioma. Si quieres corregir una traducción al inglés, modifica el `msgstr` en `locale/en/LC_MESSAGES/minecraft-afk.po`. Para ajustar únicamente la redacción visible en español, modifica su equivalente en `locale/es/LC_MESSAGES/minecraft-afk.po`. Conserva el `msgid` cuando el mensaje original no cambia: es la clave que conecta el catálogo con el código.

Por ejemplo, esta entrada del catálogo inglés corresponde al aviso que se muestra antes de iniciar el minado. Puedes mejorar la frase de `msgstr` sin modificar los controles ni las traducciones de otros idiomas:

```po
msgid "Listo para iniciar"
msgstr "Ready to start"
```

Después de editar solamente una traducción, ejecuta `python3 scripts/translations.py compile` y `python3 scripts/translations.py check`, reinicia la aplicación y revisa el mensaje en su contexto. Los archivos `.mo` se generan a partir de los `.po`; no se editan directamente. Un mensaje con valores como `{seconds:.3f}`, `{error}` o `%s` debe conservar esos marcadores y sus formatos. Traduce las palabras que los rodean y comprueba que los valores sigan apareciendo correctamente.

Si necesitas cambiar el significado o el texto base compartido, localiza primero el mensaje en el código y modifica el literal dentro de `_()`, `N_()` o `message`. Después ejecuta el flujo completo de [mantenimiento de catálogos](#mantener-los-catálogos-de-traducción). Un cambio de `msgid` se considera un mensaje nuevo: `update` no reutiliza traducciones por coincidencia aproximada, por lo que tendrás que revisar y completar la nueva entrada en todos los idiomas. Puedes encontrar las apariciones de un texto con:

```bash
rg -n --fixed-strings 'Listo para iniciar' minecraft_afk scripts locale \
  -g '*.py' -g '*.sh' -g '*.po'
```

## Contribuir con un idioma nuevo

Actualmente la aplicación registra español (`es`) e inglés (`en`). Para añadir otro idioma hay que crear su catálogo y registrarlo en el código, el selector y las herramientas de verificación. El ejemplo de esta sección utiliza portugués (`pt`) como referencia para una futura contribución; ese idioma todavía no forma parte de la aplicación. Antes de empezar, comprueba que puedes revisar la traducción completa y elige un código coherente para el catálogo, los ajustes y las pruebas.

Primero actualiza la plantilla con los idiomas actuales y crea el catálogo nuevo. Haz este paso antes de añadir `pt` a `LANGUAGES`, porque la herramienta de actualización espera que exista el archivo `.po` de cada idioma registrado. `msginit`, incluido en las herramientas de GNU gettext, crea la cabecera inicial y las entradas a partir de la plantilla:

```bash
python3 scripts/translations.py update
mkdir -p locale/pt/LC_MESSAGES
msginit --input=locale/minecraft-afk.pot \
  --output-file=locale/pt/LC_MESSAGES/minecraft-afk.po \
  --locale=pt --no-translator
```

Completa los `msgstr` del nuevo archivo y revisa los campos `Language`, `Content-Type` y `Plural-Forms` de su cabecera. Conserva UTF-8 y utiliza las reglas plurales del idioma correspondiente. Los nombres de los archivos deben seguir siendo `minecraft-afk.po` y `minecraft-afk.mo`, porque la carga de traducciones usa ese dominio. El catálogo debe cubrir los controles, los errores, las ayudas de consola y los mensajes de ejecución; una traducción incompleta hará fallar la comprobación de cobertura.

Después registra el idioma en los puntos que aparecen en esta tabla. La implementación actual contiene algunas listas explícitas de idiomas, de modo que crear la carpeta del catálogo por sí sola no lo habilita:

| Archivo | Cambio necesario |
| --- | --- |
| [`minecraft_afk/i18n.py`](minecraft_afk/i18n.py) | Añade `pt` a `SUPPORTED_LANGUAGES` y a las dos comprobaciones de idiomas admitidos de `resolve_language()`: selección explícita y detección automática. Conserva `auto` como preferencia y español como idioma de reserva. |
| [`minecraft_afk/window.py`](minecraft_afk/window.py) | Añade `self.language_combo.append("pt", "Português")` junto a las opciones existentes en `_build_settings_page()`. Utiliza el nombre del idioma en su propia lengua. |
| [`scripts/translations.py`](scripts/translations.py) | Incorpora `pt` a `LANGUAGES` y actualiza el mensaje final, que actualmente enumera `es, en`, para que refleje los idiomas procesados. |
| [`tests/test_i18n.py`](tests/test_i18n.py) | Amplía las comprobaciones de selección, catálogos, mensajes Bash y resultados numéricos. Actualiza los casos que trataban al idioma nuevo como no disponible; por ejemplo, `pt_BR:en_GB:es` deberá preferir `pt` cuando se registre. |
| [`tests/test_gui_i18n.py`](tests/test_gui_i18n.py) | Comprueba la opción nueva, su persistencia al reiniciar, las etiquetas y los estados del temporizador. |
| [`README.md`](README.md) y esta guía | Actualiza los idiomas disponibles, las rutas de los catálogos y los ejemplos que hayan cambiado. |

La detección actual reduce variantes regionales como `pt_BR` y `pt_PT` al código base `pt`. Si necesitas catálogos regionales diferentes, tendrás que ampliar esa resolución y sus pruebas, además de definir qué variante se usa cuando no existe una coincidencia exacta. También conviene mantener una única fuente de idiomas admitidos si refactorizas el registro, para reducir el riesgo de que el selector, la detección y la herramienta de compilación acepten listas distintas.

Una vez registrado el idioma, ejecuta `update`, completa las entradas nuevas que aparezcan, ejecuta `compile` y `check`, y revisa la aplicación en el idioma añadido. Prueba tanto la selección explícita como la automática y confirma que los cálculos y los datos `clave=valor` conservan sus resultados. Incluye el nuevo `.po`, su `.mo`, la plantilla actualizada y los cambios de registro, documentación y pruebas en la misma contribución.

## Mantener los catálogos de traducción

Los mensajes visibles se escriben en español como texto base y se incluyen en los catálogos de español e inglés. En Python, utiliza `_("Texto completo")` y aplica los valores después de traducir, por ejemplo `_("Tiempo: {seconds} s").format(seconds=value)`. Las etiquetas que se almacenan antes de seleccionar el idioma se marcan con `N_()` y se traducen con `_()` al mostrarse. En Bash, utiliza mensajes literales como `message 'Tiempo: %s s' "$seconds"`. Conserva los marcadores, sus nombres y sus formatos para que la traducción pueda cambiar el orden de la frase sin perder información.

Después de añadir o cambiar mensajes, ejecuta `update` para actualizar la plantilla y las entradas de los catálogos. Completa los nuevos `msgstr` en `locale/es/LC_MESSAGES/minecraft-afk.po` y `locale/en/LC_MESSAGES/minecraft-afk.po`, manteniendo el español en el primero y su traducción al inglés en el segundo. A continuación, compila y verifica los archivos. Incluye en la contribución la plantilla y los catálogos fuente y compilados que hayan cambiado, ya que la aplicación debe poder iniciarse sin generar traducciones durante su ejecución.

```bash
python3 scripts/translations.py update
# Edita y completa los dos catálogos .po antes de continuar.
python3 scripts/translations.py compile
python3 scripts/translations.py check
```

Redacta mensajes completos y evita construir una oración con fragmentos traducidos por separado. Si una cantidad necesita formas de singular y plural, amplía la capa de traducción para usar `ngettext` sobre el catálogo activo e incorpora las entradas plurales y sus pruebas. Revisa también que las etiquetas y los avisos se entiendan en todos los idiomas registrados y que el texto quepa en la interfaz. El cambio de idioma se aplica al reiniciar; una contribución debe conservar este comportamiento o explicar y comprobar cualquier modificación de ese flujo.

## Verificar los cambios

Ejecuta las comprobaciones que correspondan al cambio. La suite general valida la selección de idioma, la persistencia, los mensajes de consola y la estabilidad de los resultados numéricos; las pruebas GTK se omiten por defecto. La comprobación de catálogos detecta mensajes pendientes, incompatibilidades de formato en Python y archivos `.mo` desactualizados. La suite también comprueba los marcadores utilizados en los mensajes Bash. Desde la raíz del proyecto puedes ejecutar:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/translations.py check
bash -n scripts/minecraft-afk.sh scripts/mob-farm.sh scripts/stone-farm.sh scripts/i18n.sh
git diff --check
```

Cuando modifiques controles, temporizadores o el selector de idioma, ejecuta además las pruebas GTK en una sesión gráfica. Estas utilizan configuración temporal y sustituyen las acciones que iniciarían las granjas. Complementa la comprobación automática con una revisión visual en español e inglés si cambias tamaños, distribución o textos largos; comprueba que la información siga siendo legible y que los botones importantes sean accesibles.

```bash
MINECRAFT_AFK_GUI_TESTS=1 /usr/bin/python3 -m unittest discover -s tests -p test_gui_i18n.py -v
```

Si corriges un fallo de comportamiento, añade una prueba que reproduzca el problema cuando sea práctico y comprueba que pasa con la corrección. Para cambios de documentación, revisa los enlaces, los nombres de los archivos y los ejemplos de comandos. Describe en la pull request qué verificaste y cualquier comprobación que no pudiste realizar, con el motivo correspondiente.

Para una corrección de traducción, verifica el mensaje en la pantalla o en el comando donde aparece, conserva sus variables y confirma que el `.mo` está actualizado. Para un idioma nuevo, añade pruebas de detección y persistencia, compara los resultados numéricos con los idiomas existentes y revisa las distintas fases del temporizador. Si cambias el comportamiento de una granja, comprueba las condiciones de inicio y parada mediante simulaciones que sustituyan las acciones del ratón. La comprobación debe demostrar el comportamiento que cambió, además de confirmar que la aplicación sigue iniciándose.

## Actualizar documentación e imágenes

Mantén el README orientado a instalar y utilizar la aplicación, y utiliza esta guía para explicar cómo modificarla y contribuir. Escribe párrafos completos con una idea principal, conserva los nombres de los controles tal como aparecen en la interfaz y acompaña los comandos con el contexto necesario para ejecutarlos. Cuando cambies el título de una sección, actualiza también su enlace en la tabla de contenidos. Los ejemplos deben indicar si abren una ventana, modifican archivos o inician una automatización.

El README tiene un espacio reservado para un banner y un comentario con la línea Markdown preparada. Para añadirlo, crea `docs/assets/` si todavía no existe, guarda la imagen como `banner.png` o ajusta la ruta a su nombre real, coloca la línea de imagen fuera del comentario y elimina el párrafo reservado. Utiliza un archivo con un tamaño razonable y un texto alternativo descriptivo. Si añades capturas, procura que muestren el comportamiento que explicas y que no incluyan información personal ajena al ejemplo.

## Resolver problemas frecuentes

**La aplicación sigue mostrando la traducción anterior.** Comprueba que editaste el `.po` del idioma seleccionado, ejecuta `python3 scripts/translations.py compile` y cierra y vuelve a abrir la ventana. Los archivos `.mo` son los que carga la aplicación al iniciar. Si cambiaste el texto base, revisa que el catálogo tenga exactamente el nuevo `msgid`; una clave diferente no encontrará la traducción esperada. Recuerda también que el idioma explícito de Ajustes tiene prioridad sobre el idioma del sistema.

**La validación del catálogo falla.** Un mensaje pendiente suele indicar un `msgstr` vacío, una entrada nueva sin completar o una traducción marcada como `fuzzy` que todavía necesita revisión. Un error de formato requiere comparar los marcadores del original y la traducción, incluidos nombres como `{seconds}` y especificadores como `:.3f`. Si el error indica que el catálogo compilado está desactualizado, vuelve a ejecutar `compile`. Si `update` no encuentra el `.po` de un idioma recién registrado, créalo con `msginit` a partir de la plantilla antes de repetir la actualización.

**GTK no se puede importar o no encuentra una pantalla.** En el primer caso, comprueba que `python3-gi` y `gir1.2-gtk-3.0` estén instalados y utiliza `/usr/bin/python3`, o un entorno que tenga acceso a esos paquetes. En el segundo, ejecuta las pruebas GTK dentro de una sesión gráfica o de una pantalla virtual configurada para ese fin. La suite general omite esas pruebas cuando `MINECRAFT_AFK_GUI_TESTS` no está activada; una prueba omitida no confirma que la interfaz haya sido revisada. Si `xdotool` no controla Minecraft durante una comprobación manual, verifica que la sesión sea X11 y que la ventana del juego esté preparada para recibir las acciones.

## Enviar la contribución

Antes de abrir una pull request, revisa el diff y comprueba que contiene los archivos relacionados con el cambio. Escribe un título concreto y una descripción que explique el problema, el comportamiento resultante y cómo lo validaste. Enlaza la incidencia asociada cuando exista y añade capturas si ayudan a revisar un cambio visual. Organiza los commits de forma que su propósito sea reconocible y evita incluir configuraciones personales, registros de ejecución o archivos temporales.

Selecciona los archivos con `git add`, inspecciona el contenido preparado con `git diff --cached` y crea un commit que describa la aportación. Publica la rama en tu fork, o en el repositorio si tienes permisos, y abre la pull request contra la rama principal del proyecto. El siguiente ejemplo corresponde a una contribución que modifica únicamente esta guía; para cambios de código o de idiomas, selecciona los archivos correspondientes, incluidos los catálogos compilados cuando proceda:

```bash
git status --short
git diff -- CONTRIBUTING.md
git add -- CONTRIBUTING.md
git diff --cached
git commit -m "docs: ampliar la guía de contribución"
git push -u origin HEAD
```

La descripción debe permitir revisar el resultado sin reconstruir toda la conversación de la incidencia. Explica el problema original, qué cambió y qué pruebas o comprobaciones visuales realizaste. Si incorporas un idioma, identifica su código, las variantes regionales que resuelve y cómo revisaste la traducción. Si algún comportamiento queda pendiente, descríbelo de forma concreta para que la persona que revise la contribución conozca su alcance.

## Participar en la revisión y respetar la licencia

Durante la revisión, responde a las observaciones con el contexto necesario para entender las decisiones y actualiza la documentación cuando cambie el alcance. Las contribuciones forman parte de un proyecto distribuido bajo la [licencia MIT](LICENSE); conserva los avisos de copyright aplicables y la atribución de cualquier material que incorpores. Puedes volver al [README](README.md) para consultar las instrucciones de uso y el comportamiento esperado de las granjas.

Mantén la discusión centrada en el cambio y explica tus razones cuando propongas otra solución. Si actualizas la rama después de recibir comentarios, indica qué observaciones resolviste y repite las verificaciones afectadas por esa revisión. Incluye código, textos e imágenes que puedas aportar al proyecto y documenta las atribuciones de terceros cuando correspondan.
