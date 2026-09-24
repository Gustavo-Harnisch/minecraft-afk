#!/usr/bin/env python3
"""Render one gettext message for Bash without changing machine output."""

import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from minecraft_afk.i18n import _, set_language


def main() -> None:
    set_language(os.environ.get("MINECRAFT_AFK_LANGUAGE", "auto"))
    template = _(sys.argv[1])
    arguments = tuple(sys.argv[2:])
    print(template % arguments if arguments else template)


if __name__ == "__main__":
    main()
