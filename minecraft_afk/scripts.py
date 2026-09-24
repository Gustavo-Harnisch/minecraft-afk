"""Registro, construcción y ejecución de comandos Bash."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shlex
import subprocess

from .config import ProjectPaths
from .i18n import _


@dataclass(frozen=True)
class ScriptAction:
    """Acción Bash reutilizable por la interfaz."""

    label: str
    script: str
    arguments: tuple[str, ...] = ()


@dataclass(frozen=True)
class CommandResult:
    command: str
    returncode: int
    stdout: str
    stderr: str

    @property
    def output(self) -> str:
        parts = [part.strip() for part in (self.stdout, self.stderr) if part.strip()]
        return "\n".join(parts)


class BashScriptRunner:
    """Resuelve scripts y los ejecuta sin usar una terminal interactiva."""

    def __init__(self, paths: ProjectPaths | None = None) -> None:
        self.paths = paths or ProjectPaths.default()
        self.language = "auto"
        self._scripts: dict[str, Path] = {}
        self.register("minecraft-afk", "minecraft-afk.sh")
        self.register("mob-farm", "mob-farm.sh")
        self.register("stone-farm", "stone-farm.sh")

    def register(self, name: str, filename: str) -> None:
        script_path = (self.paths.scripts / filename).resolve()
        scripts_dir = self.paths.scripts.resolve()
        try:
            script_path.relative_to(scripts_dir)
        except ValueError as error:
            raise ValueError(_("El script debe estar dentro de la carpeta scripts")) from error
        self._scripts[name] = script_path

    def available_scripts(self) -> tuple[str, ...]:
        return tuple(self._scripts)

    def build_argv(self, name: str, *arguments: object) -> list[str]:
        try:
            script_path = self._scripts[name]
        except KeyError as error:
            available = ", ".join(self.available_scripts()) or _("ninguno")
            raise ValueError(
                _("Script desconocido: {name}. Disponibles: {available}").format(
                    name=name, available=available)
            ) from error
        return ["bash", str(script_path), *(str(value) for value in arguments)]

    def build_command(self, name: str, *arguments: object) -> str:
        return shlex.join(self.build_argv(name, *arguments))

    def execute(
        self,
        name: str,
        *arguments: object,
        timeout: float = 10.0,
    ) -> CommandResult:
        argv = self.build_argv(name, *arguments)
        completed = subprocess.run(
            argv,
            cwd=self.paths.root,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
            env={**os.environ, "MINECRAFT_AFK_LANGUAGE": self.language},
        )
        return CommandResult(
            command=shlex.join(argv),
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
