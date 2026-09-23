#!/usr/bin/env bash
set -u

# Fuerza el punto como separador decimal en awk/printf. Esto evita que
# locales como es_CL/es_ES escriban 657,45 en el archivo de estado, valor
# que Python no puede interpretar directamente como float.
export LC_NUMERIC=C

readonly MINECRAFT_EDITION="Java Edition"
readonly MINECRAFT_VERSION="vanilla 1.21+"
readonly BLOCK_NAME="Stone"
readonly BLOCK_HARDNESS="1.5"
readonly CONTINUOUS_BREAK_DELAY="0.30"
readonly PIDFILE="${MINECRAFT_AFK_PIDFILE:-/tmp/minecraft-afk.pid}"
readonly STATEFILE="${MINECRAFT_AFK_STATEFILE:-/tmp/minecraft-afk.state}"
readonly START_DELAY_SECONDS="20"

pid=""
pickaxe_key="diamond"
pickaxe_label=""
pickaxe_speed=""
max_durability=""
current_durability="1561"
minimum_durability="100"
efficiency="0"
unbreaking="0"
haste="0"
calculation_method="calibrated"
calibrated_seconds_per_durability="1.474"
seconds_per_durability=""
auto_stop="1"
final_speed=""
progress_per_tick=""
break_ticks=""
break_seconds=""
instant_break="0"
continuous_cycle_seconds=""
durability_to_spend=""
expected_blocks=""
estimated_duration_seconds=""
start_epoch=""

usage() {
    cat <<'EOF'
Uso:
  stone-farm.sh start [opciones]
  stone-farm.sh calibrate --seconds 1-60 --initial-durability ENTERO
  stone-farm.sh calculate [opciones]
  stone-farm.sh stop
  stone-farm.sh status
  stone-farm.sh table

Opciones:
  --pickaxe wood|stone|iron|gold|diamond|netherite
  --current-durability ENTERO
  --minimum-durability ENTERO
  --efficiency 0-5
  --unbreaking 0-3
  --haste 0-2
  --calculation-method theoretical|calibrated
  --calibrated-seconds-per-durability DECIMAL
  --auto-stop 0|1

Calibración:
  --seconds 1-60
  --initial-durability ENTERO

La Stone Farm mantiene el botón izquierdo presionado continuamente. Si
--auto-stop es 1, lo libera automáticamente al cumplirse el tiempo estimado
para llegar a la durabilidad mínima.
EOF
}

is_running() {
    [ -f "$PIDFILE" ] || return 1
    pid=$(sed -n '1p' "$PIDFILE")
    case "$pid" in ''|*[!0-9]*) return 1 ;; esac
    kill -0 "$pid" 2>/dev/null
}

release_mouse() {
    if command -v xdotool >/dev/null 2>&1; then
        xdotool mouseup 1 >/dev/null 2>&1 || true
    fi
}

cleanup_files() {
    rm -f "$PIDFILE" "$STATEFILE"
}

require_dependencies() {
    if ! command -v xdotool >/dev/null 2>&1; then
        echo "Error: xdotool no está instalado." >&2
        echo "Instálalo con: sudo apt install xdotool" >&2
        return 1
    fi
}

set_pickaxe() {
    case "$1" in
        wood) pickaxe_label="Pico de madera"; pickaxe_speed="2"; max_durability="59" ;;
        stone) pickaxe_label="Pico de piedra"; pickaxe_speed="4"; max_durability="131" ;;
        iron) pickaxe_label="Pico de hierro"; pickaxe_speed="6"; max_durability="250" ;;
        gold) pickaxe_label="Pico de oro"; pickaxe_speed="12"; max_durability="32" ;;
        diamond) pickaxe_label="Pico de diamante"; pickaxe_speed="8"; max_durability="1561" ;;
        netherite) pickaxe_label="Pico de netherita"; pickaxe_speed="9"; max_durability="2031" ;;
        *)
            echo "Pico desconocido: $1" >&2
            return 1
            ;;
    esac
}

validate_binary() {
    [[ "$2" == "0" || "$2" == "1" ]] || {
        echo "Error: $1 debe ser 0 o 1." >&2
        return 1
    }
}

validate_range() {
    local name="$1" value="$2" minimum="$3" maximum="$4"
    if ! [[ "$value" =~ ^[0-9]+$ ]] || (( value < minimum || value > maximum )); then
        echo "Error: $name debe estar entre $minimum y $maximum." >&2
        return 1
    fi
}

validate_nonnegative_integer() {
    local name="$1" value="$2"
    if ! [[ "$value" =~ ^[0-9]+$ ]]; then
        echo "Error: $name debe ser un entero >= 0." >&2
        return 1
    fi
}

validate_positive_decimal() {
    local name="$1" value="$2"
    value="${value/,/.}"
    if ! [[ "$value" =~ ^[0-9]+([.][0-9]+)?$ ]] || ! awk -v value="$value" 'BEGIN { exit !(value > 0) }'; then
        echo "Error: $name debe ser un número mayor que 0." >&2
        return 1
    fi
}

parse_options() {
    pickaxe_key="diamond"
    current_durability="1561"
    minimum_durability="100"
    efficiency="0"
    unbreaking="0"
    haste="0"
    calculation_method="calibrated"
    calibrated_seconds_per_durability="1.474"
    auto_stop="1"

    while (($# > 0)); do
        case "$1" in
            --pickaxe|-p) (($# >= 2)) || return 1; pickaxe_key="$2"; shift 2 ;;
            --current-durability|--durability) (($# >= 2)) || return 1; current_durability="$2"; shift 2 ;;
            --minimum-durability|--min-durability) (($# >= 2)) || return 1; minimum_durability="$2"; shift 2 ;;
            --efficiency) (($# >= 2)) || return 1; efficiency="$2"; shift 2 ;;
            --unbreaking) (($# >= 2)) || return 1; unbreaking="$2"; shift 2 ;;
            --haste) (($# >= 2)) || return 1; haste="$2"; shift 2 ;;
            --calculation-method) (($# >= 2)) || return 1; calculation_method="$2"; shift 2 ;;
            --calibrated-seconds-per-durability) (($# >= 2)) || return 1; calibrated_seconds_per_durability="$2"; shift 2 ;;
            --auto-stop) (($# >= 2)) || return 1; auto_stop="$2"; shift 2 ;;
            --help|-h) usage; exit 0 ;;
            *) echo "Opción desconocida: $1" >&2; usage >&2; return 1 ;;
        esac
    done

    set_pickaxe "$pickaxe_key" || return 1
    validate_nonnegative_integer "current-durability" "$current_durability" || return 1
    validate_nonnegative_integer "minimum-durability" "$minimum_durability" || return 1
    validate_range "Efficiency" "$efficiency" 0 5 || return 1
    validate_range "Unbreaking" "$unbreaking" 0 3 || return 1
    validate_range "Haste" "$haste" 0 2 || return 1
    case "$calculation_method" in
        theoretical|calibrated) ;;
        *) echo "Error: calculation-method debe ser theoretical o calibrated." >&2; return 1 ;;
    esac
    calibrated_seconds_per_durability="${calibrated_seconds_per_durability/,/.}"
    validate_positive_decimal "calibrated-seconds-per-durability" "$calibrated_seconds_per_durability" || return 1
    validate_binary "auto-stop" "$auto_stop" || return 1

    if (( current_durability < 1 )); then
        echo "Error: current-durability debe ser al menos 1." >&2
        return 1
    fi
    if (( current_durability > max_durability )); then
        echo "Error: la durabilidad máxima de $pickaxe_label es $max_durability." >&2
        return 1
    fi
    if (( minimum_durability >= current_durability )); then
        echo "Error: minimum-durability debe ser menor que current-durability." >&2
        return 1
    fi
}

calculate_plan() {
    local effective_speed="$pickaxe_speed"

    if (( efficiency > 0 )); then
        effective_speed=$(awk -v speed="$effective_speed" -v level="$efficiency" \
            'BEGIN { printf "%.8f", speed + level * level + 1 }')
    fi

    effective_speed=$(awk -v speed="$effective_speed" -v level="$haste" \
        'BEGIN { printf "%.8f", speed * (1 + 0.2 * level) }')

    final_speed=$(awk -v speed="$effective_speed" 'BEGIN { printf "%.8f", speed }')
    progress_per_tick=$(awk -v speed="$final_speed" -v hardness="$BLOCK_HARDNESS" \
        'BEGIN { printf "%.12f", speed / hardness / 30 }')

    if awk -v progress="$progress_per_tick" 'BEGIN { exit !(progress > 1) }'; then
        instant_break="1"
        break_ticks="1"
        break_seconds="0.05"
        continuous_cycle_seconds="0.05"
    else
        instant_break="0"
        break_ticks=$(awk -v progress="$progress_per_tick" \
            'BEGIN { print int(1 / progress + 0.999999999) }')
        break_seconds=$(awk -v ticks="$break_ticks" 'BEGIN { printf "%.2f", ticks / 20 }')
        continuous_cycle_seconds=$(awk -v seconds="$break_seconds" -v delay="$CONTINUOUS_BREAK_DELAY" \
            'BEGIN { printf "%.2f", seconds + delay }')
    fi

    durability_to_spend=$((current_durability - minimum_durability))
    expected_blocks=$((durability_to_spend * (unbreaking + 1)))

    if [[ "$calculation_method" == "calibrated" ]]; then
        seconds_per_durability=$(awk -v seconds="$calibrated_seconds_per_durability" \
            'BEGIN { printf "%.6f", seconds }')
    else
        seconds_per_durability=$(awk -v cycle="$continuous_cycle_seconds" -v multiplier="$((unbreaking + 1))" \
            'BEGIN { printf "%.6f", cycle * multiplier }')
    fi
    estimated_duration_seconds=$(awk -v durability="$durability_to_spend" -v seconds="$seconds_per_durability" \
        'BEGIN { printf "%.2f", durability * seconds }')
}

configure_from_args() {
    parse_options "$@" || return 1
    calculate_plan
}

print_machine_configuration() {
    printf 'edition=%s\n' "$MINECRAFT_EDITION"
    printf 'version=%s\n' "$MINECRAFT_VERSION"
    printf 'block=%s\n' "$BLOCK_NAME"
    printf 'hardness=%s\n' "$BLOCK_HARDNESS"
    printf 'pickaxe_key=%s\n' "$pickaxe_key"
    printf 'pickaxe=%s\n' "$pickaxe_label"
    printf 'max_durability=%s\n' "$max_durability"
    printf 'current_durability=%s\n' "$current_durability"
    printf 'minimum_durability=%s\n' "$minimum_durability"
    printf 'durability_to_spend=%s\n' "$durability_to_spend"
    printf 'efficiency=%s\n' "$efficiency"
    printf 'unbreaking=%s\n' "$unbreaking"
    printf 'haste=%s\n' "$haste"
    printf 'calculation_method=%s\n' "$calculation_method"
    printf 'calibrated_seconds_per_durability=%s\n' "$calibrated_seconds_per_durability"
    printf 'seconds_per_durability=%s\n' "$seconds_per_durability"
    printf 'final_speed=%s\n' "$final_speed"
    printf 'progress_per_tick=%s\n' "$progress_per_tick"
    printf 'break_ticks=%s\n' "$break_ticks"
    printf 'break_seconds=%s\n' "$break_seconds"
    printf 'instant_break=%s\n' "$instant_break"
    printf 'continuous_cycle_seconds=%s\n' "$continuous_cycle_seconds"
    printf 'expected_blocks=%s\n' "$expected_blocks"
    printf 'estimated_duration_seconds=%s\n' "$estimated_duration_seconds"
    printf 'auto_stop=%s\n' "$auto_stop"
    printf 'start_delay_seconds=%s\n' "$START_DELAY_SECONDS"
}

write_state() {
    # Escribe primero en un archivo temporal y después lo mueve de una sola vez.
    # Así la GUI nunca alcanza a leer un estado parcialmente escrito.
    local tmp_state="${STATEFILE}.tmp.$$"
    {
        printf 'mode=stone_farm\n'
        printf 'mode_label=Stone Mining Farm\n'
        printf 'run_type=normal\n'
        print_machine_configuration
        printf 'start_epoch=%s\n' "$start_epoch"
    } > "$tmp_state"
    mv -f -- "$tmp_state" "$STATEFILE"
}

start_command() {
    if is_running; then
        echo "Minecraft AFK ya está activo (PID $pid)."
        status_command
        return 0
    fi

    configure_from_args "$@" || return 1
    require_dependencies || return 1
    # El tiempo real de minado comienza DESPUÉS de los 20 segundos.
    start_epoch=$(awk -v now="$(date +%s.%N)" -v delay="$START_DELAY_SECONDS" \
        'BEGIN { printf "%.3f", now + delay }')

    (
        trap 'release_mouse; cleanup_files' EXIT
        trap 'exit 0' INT TERM

        # Tiempo para volver a Minecraft y apuntar al bloque.
        sleep "$START_DELAY_SECONDS"

        # A partir de aquí comienza realmente el minado.
        xdotool mousedown 1
        if [[ "$auto_stop" == "1" ]]; then
            sleep "$estimated_duration_seconds"
        else
            while true; do
                sleep 3600
            done
        fi
    ) >/dev/null 2>&1 &

    pid=$!
    printf '%s\n' "$pid" > "$PIDFILE"
    write_state

    echo "Stone Mining Farm iniciada (PID $pid)."
    echo "El minado comenzará en $START_DELAY_SECONDS segundos."
    echo "Clic izquierdo mantenido. Pico: $pickaxe_label."
    echo "Durabilidad: $current_durability → $minimum_durability | bloques estimados: $expected_blocks"
    echo "Segundos/durabilidad: $seconds_per_durability s."
    if [[ "$calculation_method" == "calibrated" ]]; then
        echo "Método: calibrado (incluye el retraso real de la farm)."
    else
        echo "Método: teórico."
    fi
    if [[ "$auto_stop" == "1" ]]; then
        echo "Auto-stop en aproximadamente $estimated_duration_seconds s."
    else
        echo "Auto-stop desactivado; usa Detener para liberar el clic."
    fi
}

calibrate_command() {
    if is_running; then
        echo "Minecraft AFK ya está activo (PID $pid)."
        status_command
        return 0
    fi

    local calibration_seconds="30"
    local initial_durability=""

    while (($# > 0)); do
        case "$1" in
            --seconds)
                (($# >= 2)) || { echo "Error: falta valor para --seconds." >&2; return 1; }
                calibration_seconds="${2/,/.}"
                shift 2
                ;;
            --initial-durability)
                (($# >= 2)) || { echo "Error: falta valor para --initial-durability." >&2; return 1; }
                initial_durability="$2"
                shift 2
                ;;
            --help|-h)
                usage
                return 0
                ;;
            *)
                echo "Opción desconocida para calibración: $1" >&2
                return 1
                ;;
        esac
    done

    validate_positive_decimal "seconds" "$calibration_seconds" || return 1
    if ! awk -v value="$calibration_seconds" 'BEGIN { exit !(value >= 1 && value <= 60) }'; then
        echo "Error: --seconds debe estar entre 1 y 60." >&2
        return 1
    fi
    validate_nonnegative_integer "initial-durability" "$initial_durability" || return 1
    if (( initial_durability < 1 )); then
        echo "Error: --initial-durability debe ser al menos 1." >&2
        return 1
    fi

    require_dependencies || return 1
    start_epoch=$(awk -v now="$(date +%s.%N)" -v delay="$START_DELAY_SECONDS" \
        'BEGIN { printf "%.3f", now + delay }')

    (
        trap 'release_mouse; cleanup_files' EXIT
        trap 'exit 0' INT TERM

        sleep "$START_DELAY_SECONDS"
        xdotool mousedown 1
        sleep "$calibration_seconds"
    ) >/dev/null 2>&1 &

    pid=$!
    printf '%s\n' "$pid" > "$PIDFILE"

    local tmp_state="${STATEFILE}.tmp.$$"
    {
        printf 'mode=stone_farm\n'
        printf 'mode_label=Calibración Stone Farm\n'
        printf 'run_type=calibration\n'
        printf 'current_durability=%s\n' "$initial_durability"
        printf 'calibration_duration_seconds=%s\n' "$calibration_seconds"
        printf 'estimated_duration_seconds=%s\n' "$calibration_seconds"
        printf 'auto_stop=1\n'
        printf 'start_delay_seconds=%s\n' "$START_DELAY_SECONDS"
        printf 'start_epoch=%s\n' "$start_epoch"
    } > "$tmp_state"
    mv -f -- "$tmp_state" "$STATEFILE"

    echo "Calibración iniciada (PID $pid)."
    echo "Tienes $START_DELAY_SECONDS segundos para volver a Minecraft y apuntar al bloque."
    echo "Después mantendrá el clic izquierdo durante $calibration_seconds segundos y se detendrá automáticamente."
    echo "Durabilidad inicial registrada: $initial_durability."
}

stop_command() {
    if is_running; then
        kill "$pid" 2>/dev/null || true
        sleep 0.08
    fi
    cleanup_files
    release_mouse
    echo "Minecraft AFK detenido. Botón izquierdo liberado."
}

status_command() {
    if is_running; then
        echo "Minecraft AFK está activo (PID $pid)."
        [ -f "$STATEFILE" ] && sed 's/^/  /' "$STATEFILE"
    else
        cleanup_files
        release_mouse
        echo "Minecraft AFK está detenido."
    fi
}

reference_table() {
    cat <<'EOF'
Durabilidad máxima de picos vanilla (Java Edition):

  Madera       59
  Piedra      131
  Hierro      250
  Oro          32
  Diamante   1561
  Netherita  2031

Unbreaking en herramientas multiplica la duración esperada por (nivel + 1),
pero es aleatorio. El temporizador es por ello una estimación cuando
Unbreaking > 0.
EOF
}

command="${1:-help}"
shift || true
case "$command" in
    start) start_command "$@" ;;
    calibrate|calibration) calibrate_command "$@" ;;
    calculate|calc) configure_from_args "$@" && print_machine_configuration ;;
    stop|emergency-stop) stop_command ;;
    status) status_command ;;
    table|reference) reference_table ;;
    help|-h|--help) usage ;;
    *) echo "Comando desconocido: $command" >&2; usage >&2; exit 1 ;;
esac
