# Minecraft AFK — GUI

Aplicación gráfica para Linux Mint que controla automatizaciones AFK de Minecraft sin pedir configuración en la terminal.

```text
GUI GTK3 → Python → scripts Bash → xdotool
```

La interfaz incluye pestañas para **Mob Farm**, **Stone Farm**, **Estado**, **Logs** y **Ajustes**.

## Requisitos

En Linux Mint / Ubuntu / Debian:

```bash
sudo apt update
sudo apt install python3 python3-gi gir1.2-gtk-3.0 xdotool
```

`xdotool` funciona principalmente en sesiones X11. En Wayland puede no controlar el ratón correctamente.

## Ejecutar

```bash
python3 main.py
```

Toda la configuración normal se realiza desde la GUI.

## Mob Farm

Permite elegir el intervalo entre ataques.

```bash
./scripts/mob-farm.sh start --interval 2.00
```

## Stone Farm

Stone Farm está diseñada para una granja continua de piedra. Al iniciarla, el script ejecuta una sola vez:

```bash
xdotool mousedown 1
```

y mantiene el botón izquierdo presionado hasta que:

- se cumple el temporizador y Auto-stop está activado; o
- el usuario pulsa **Detener** / **Detener todo**.

Al detenerse siempre ejecuta `xdotool mouseup 1`.

### Configuración desde la GUI

- Pico: madera, piedra, hierro, oro, diamante o netherita.
- Durabilidad actual.
- Durabilidad mínima objetivo.
- Efficiency 0–5.
- Unbreaking 0–3.
- Haste 0–2.
- Método de cálculo: **Calibrado** para una cobblestone farm real o **Teórico**.
- Modo calibración mediante toggle, con una prueba automática de 1 a 60 segundos.
- Botón especial **INICIAR CALIBRACIÓN** separado del minado normal.
- Auto-stop.

La GUI muestra inmediatamente:

- durabilidad máxima del pico;
- durabilidad que se pretende consumir;
- bloques estimados;
- tiempo medio estimado por bloque manteniendo el clic;
- tiempo estimado hasta la durabilidad mínima;
- temporizador restante cuando la farm está activa.

Ejemplo:

```bash
./scripts/stone-farm.sh start \
  --pickaxe diamond \
  --current-durability 1200 \
  --minimum-durability 100 \
  --efficiency 5 \
  --unbreaking 3 \
  --haste 2 \
  --calculation-method calibrated \
  --calibrated-seconds-per-durability 1.474 \
  --auto-stop 1
```

Consultar el cálculo sin iniciar:

```bash
./scripts/stone-farm.sh calculate \
  --pickaxe diamond \
  --current-durability 1200 \
  --minimum-durability 100 \
  --efficiency 5 \
  --unbreaking 3 \
  --haste 2
```

La salida usa pares `clave=valor`.


### Modo calibrado para Cobblestone Farm

El modo recomendado para una granja generada con agua + lava es **Calibrado**. En este modo el temporizador no supone que siempre exista un bloque listo: usa una medición real de cuántos segundos tarda la granja en consumir un punto de durabilidad.

La calibración incluida por defecto proviene de esta prueba:

```text
Durabilidad antes:   962
Durabilidad después: 943
Duración:             28 s
Puntos consumidos:    19
Calibración:          28 / 19 = 1.474 s por durabilidad
```

Por ejemplo, para 962 → 900:

```text
62 puntos × 1.474 s ≈ 91.4 s ≈ 01:31
```

Para medir una nueva granja, activa el toggle **Modo calibración**, indica un tiempo de prueba entre **1 y 60 segundos** y comprueba la durabilidad inicial. Al pulsar **INICIAR CALIBRACIÓN**, la GUI muestra los 20 segundos de preparación, mantiene el clic izquierdo exactamente durante el tiempo indicado y lo libera automáticamente. Al terminar, escribe la durabilidad final y pulsa **CALCULAR Y GUARDAR CALIBRACIÓN**.

Los 20 segundos de preparación no forman parte de la medición. Por ejemplo, una prueba configurada a 30 segundos ejecuta `20 s de preparación + 30 s de minado medido`. Recalibra si cambias el diseño de la granja, el pico, Efficiency, Unbreaking, Haste o si el servidor tiene un comportamiento distinto.

## Cómo se calcula el temporizador

Stone tiene dureza 1.5. El cálculo usa la velocidad del pico, Efficiency y Haste para obtener el tiempo de rotura.

Al mantener el botón izquierdo presionado, los bloques que no son de rotura instantánea tienen además el retraso vanilla entre un bloque roto y el inicio del siguiente. En rotura instantánea se usa un tick práctico de 0.05 s por bloque.

Para la durabilidad:

```text
durabilidad a consumir = durabilidad actual - durabilidad mínima
```

Sin Unbreaking, cada bloque consume un punto de durabilidad. En herramientas con Unbreaking nivel N, el consumo es aleatorio y el número esperado de usos se multiplica por `N + 1`:

```text
bloques esperados = durabilidad a consumir × (Unbreaking + 1)
```

Por este motivo, con **Unbreaking > 0 el temporizador es una estimación estadística y no puede garantizar que el pico termine exactamente en la durabilidad mínima**.

Mending no se modela. Si el jugador recibe experiencia y el pico tiene Mending, el cálculo deja de ser fiable porque la herramienta puede repararse durante la farm.

## Durabilidad máxima vanilla

```text
Madera       59
Piedra      131
Hierro      250
Oro          32
Diamante   1561
Netherita  2031
```

La GUI ajusta automáticamente los límites de entrada según el pico seleccionado y evita que la durabilidad mínima sea igual o mayor que la actual.

## Cuenta regresiva gráfica

Al iniciar **Stone Farm**, la GUI muestra dos etapas separadas en el mismo panel:

1. **PREPARACIÓN — 20 segundos:** cuenta `00:20 → 00:00` para cambiar a Minecraft y apuntar al bloque. Durante esta etapa todavía no se presiona el botón izquierdo y no se descuenta tiempo del objetivo.
2. **MINANDO:** al terminar la preparación se ejecuta `xdotool mousedown 1` y el reloj cambia al tiempo estimado de la tarea, contando hasta `00:00`. La barra de progreso también cambia de preparación a minado.

Si Auto-stop está activo y el temporizador termina de forma natural, la GUI deja visible **OBJETIVO COMPLETADO** y el script libera el botón izquierdo. Si se usa Detener, se cancela la ejecución y se libera el clic inmediatamente.

## Estado y temporizador

La aplicación utiliza:

```text
/tmp/minecraft-afk.pid
/tmp/minecraft-afk.state
```

La pestaña **Estado** muestra el PID, modo activo, pico, objetivo de durabilidad, encantamientos, bloques estimados y el tiempo restante del auto-stop.

## Configuración persistente

Se guarda automáticamente en:

```text
~/.config/minecraft-afk/config.json
```

También respeta `XDG_CONFIG_HOME`.

## Comandos principales

```bash
./scripts/mob-farm.sh start --interval 2.0
./scripts/mob-farm.sh status
./scripts/mob-farm.sh stop

./scripts/stone-farm.sh calibrate --seconds 30 --initial-durability 962
./scripts/stone-farm.sh calculate --pickaxe diamond --current-durability 1000 --minimum-durability 100
./scripts/stone-farm.sh start --pickaxe diamond --current-durability 1000 --minimum-durability 100 --auto-stop 1
./scripts/stone-farm.sh status
./scripts/stone-farm.sh table
./scripts/stone-farm.sh stop

./minecraft-afk.sh start mob --interval 2.0
./minecraft-afk.sh start stone --pickaxe diamond --current-durability 1000 --minimum-durability 100
./minecraft-afk.sh status
./minecraft-afk.sh emergency-stop
```

## Seguridad

`emergency-stop` termina el proceso, borra los archivos temporales y ejecuta `xdotool mouseup 1` para evitar que el botón izquierdo quede presionado.

## Estructura

```text
minecraft-afk/
├── main.py
├── minecraft-afk.sh
├── minecraft_afk/
│   ├── __init__.py
│   ├── config.py
│   ├── mining.py
│   ├── scripts.py
│   ├── settings.py
│   ├── terminal.py
│   └── window.py
└── scripts/
    ├── minecraft-afk.sh
    ├── mob-farm.sh
    └── stone-farm.sh
```
