#!/usr/bin/env python3
"""Extract, compile and validate the bundled gettext catalogs (GNU gettext)."""

import argparse
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parent.parent
LOCALE = ROOT / "locale"
LANGUAGES = ("es", "en")


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def extract(target: Path) -> None:
    common = (
        "--from-code=UTF-8", "--sort-output", "--no-wrap",
        "--package-name=Minecraft AFK", "--package-version=1",
    )
    run("xgettext", *common, "--language=Python", "--keyword=_", "--keyword=N_",
        "-o", str(target), "main.py",
        *(str(path.relative_to(ROOT)) for path in sorted((ROOT / "minecraft_afk").glob("*.py"))))
    run("xgettext", *common, "--language=Shell", "--keyword=message",
        "--flag=message:1:python-format", "--join-existing", "-o", str(target),
        "scripts/minecraft-afk.sh", "scripts/mob-farm.sh", "scripts/stone-farm.sh")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("update", "compile", "check"))
    action = parser.parse_args().action
    with tempfile.TemporaryDirectory(prefix="minecraft-afk-i18n-") as directory:
        template = Path(directory) / "minecraft-afk.pot"
        if action in {"update", "check"}:
            extract(template)
        if action == "update":
            (LOCALE / "minecraft-afk.pot").write_bytes(template.read_bytes())
        for language in LANGUAGES:
            catalog = LOCALE / language / "LC_MESSAGES" / "minecraft-afk.po"
            binary = catalog.with_suffix(".mo")
            if action == "update":
                run("msgmerge", "--update", "--backup=none", "--no-fuzzy-matching",
                    "--no-wrap", str(catalog), str(template))
            elif action == "compile":
                run("msgfmt", "--check", "--check-format", "-o", str(binary), str(catalog))
            else:
                run("msgcmp", str(catalog), str(template))
                compiled = Path(directory) / f"{language}.mo"
                run("msgfmt", "--check", "--check-format", "-o", str(compiled), str(catalog))
                if not binary.exists() or binary.read_bytes() != compiled.read_bytes():
                    raise SystemExit(f"Outdated catalog: {binary}. Run: python3 scripts/translations.py compile")
    print(f"Translations: {action} OK (es, en)")


if __name__ == "__main__":
    main()
