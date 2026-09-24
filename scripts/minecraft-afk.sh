#!/usr/bin/env bash
set -u

source "$(dirname -- "${BASH_SOURCE[0]}")/i18n.sh"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
MOB_SCRIPT="$SCRIPT_DIR/mob-farm.sh"
STONE_SCRIPT="$SCRIPT_DIR/stone-farm.sh"
PIDFILE="${MINECRAFT_AFK_PIDFILE:-/tmp/minecraft-afk.pid}"
STATEFILE="${MINECRAFT_AFK_STATEFILE:-/tmp/minecraft-afk.state}"

usage() {
    message 'Uso:
  minecraft-afk.sh start mob [opciones]
  minecraft-afk.sh start stone [opciones]
  minecraft-afk.sh stop
  minecraft-afk.sh emergency-stop
  minecraft-afk.sh status
  minecraft-afk.sh table'
}

is_running() {
    [ -f "$PIDFILE" ] || return 1
    local pid
    pid=$(sed -n '1p' "$PIDFILE")
    case "$pid" in ''|*[!0-9]*) return 1 ;; esac
    kill -0 "$pid" 2>/dev/null
}

release_mouse() {
    command -v xdotool >/dev/null 2>&1 && xdotool mouseup 1 >/dev/null 2>&1 || true
}

status_command() {
    if is_running; then
        local pid
        pid=$(sed -n '1p' "$PIDFILE")
        message 'Minecraft AFK está activo (PID %s).' "$pid"
        [ -f "$STATEFILE" ] && sed 's/^/  /' "$STATEFILE"
    else
        message 'Minecraft AFK está detenido.'
    fi
}

stop_command() {
    if is_running; then
        local pid
        pid=$(sed -n '1p' "$PIDFILE")
        kill "$pid" 2>/dev/null || true
        sleep 0.05
    fi
    rm -f "$PIDFILE" "$STATEFILE"
    release_mouse
    message 'Minecraft AFK detenido.'
}

command="${1:-help}"
shift || true
case "$command" in
    start)
        mode="${1:-}"
        [[ -n "$mode" ]] && shift || true
        case "$mode" in
            mob) exec bash "$MOB_SCRIPT" start "$@" ;;
            stone) exec bash "$STONE_SCRIPT" start "$@" ;;
            *) message 'Indica un modo: mob o stone.' >&2; usage >&2; exit 1 ;;
        esac
        ;;
    stop|emergency-stop) stop_command ;;
    status) status_command ;;
    table) exec bash "$STONE_SCRIPT" table ;;
    menu) usage ;;
    help|-h|--help) usage ;;
    *) message 'Comando desconocido: %s' "$command" >&2; usage >&2; exit 1 ;;
esac
