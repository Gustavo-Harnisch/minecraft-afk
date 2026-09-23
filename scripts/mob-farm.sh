#!/usr/bin/env bash
set -u

readonly PIDFILE="${MINECRAFT_AFK_PIDFILE:-/tmp/minecraft-afk.pid}"
readonly STATEFILE="${MINECRAFT_AFK_STATEFILE:-/tmp/minecraft-afk.state}"
readonly DEFAULT_INTERVAL="2.00"

pid=""
interval="$DEFAULT_INTERVAL"

usage() {
    cat <<'EOF'
Uso:
  mob-farm.sh start [--interval N]
  mob-farm.sh stop
  mob-farm.sh status
  mob-farm.sh help
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

validate_interval() {
    local value="$1"
    [[ "$value" =~ ^[0-9]+([.][0-9]+)?$ ]] \
        && awk -v value="$value" 'BEGIN { exit !(value >= 0.01) }'
}

parse_start_args() {
    interval="$DEFAULT_INTERVAL"
    while (($# > 0)); do
        case "$1" in
            --interval|-i)
                (($# >= 2)) || { echo "Error: --interval necesita un valor." >&2; return 1; }
                interval="$2"
                shift 2
                ;;
            --help|-h)
                usage
                exit 0
                ;;
            *)
                echo "Opción desconocida: $1" >&2
                usage >&2
                return 1
                ;;
        esac
    done
    if ! validate_interval "$interval"; then
        echo "Error: el intervalo debe ser un número >= 0.01." >&2
        return 1
    fi
}

write_state() {
    {
        printf 'mode=mob_farm\n'
        printf 'mode_label=Mob Farm\n'
        printf 'interval=%s\n' "$interval"
    } > "$STATEFILE"
}

start_command() {
    if is_running; then
        echo "Minecraft AFK ya está activo (PID $pid)."
        status_command
        return 0
    fi

    parse_start_args "$@" || return 1
    require_dependencies || return 1
    write_state

    (
        trap release_mouse EXIT
        trap 'exit 0' INT TERM
        while true; do
            xdotool click 1
            sleep "$interval"
        done
    ) >/dev/null 2>&1 &

    pid=$!
    printf '%s\n' "$pid" > "$PIDFILE"
    echo "Mob Farm iniciada (PID $pid)."
    echo "Intervalo: $interval s"
}

stop_command() {
    if is_running; then
        kill "$pid" 2>/dev/null || true
        sleep 0.05
    fi
    cleanup_files
    release_mouse
    echo "Minecraft AFK detenido."
}

status_command() {
    if is_running; then
        echo "Minecraft AFK está activo (PID $pid)."
        [ -f "$STATEFILE" ] && sed 's/^/  /' "$STATEFILE"
    else
        echo "Minecraft AFK está detenido."
    fi
}

command="${1:-help}"
shift || true
case "$command" in
    start) start_command "$@" ;;
    stop|emergency-stop) stop_command ;;
    status) status_command ;;
    help|-h|--help) usage ;;
    *)
        echo "Comando desconocido: $command" >&2
        usage >&2
        exit 1
        ;;
esac
