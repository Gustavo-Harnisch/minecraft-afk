#!/usr/bin/env bash
# Shared human-readable messages. Machine output and numeric locales stay stable.
AFK_I18N_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

message() {
    if command -v python3 >/dev/null 2>&1; then
        if python3 "$AFK_I18N_DIR/translate.py" "$@"; then
            return 0
        fi
    fi
    # Keep standalone scripts usable even without the optional translator.
    printf -- "$@"
    printf '\n'
}
