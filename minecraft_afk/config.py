"""Configuración y rutas compartidas por la aplicación."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectPaths:
    root: Path
    scripts: Path
    pidfile: Path = Path("/tmp/minecraft-afk.pid")
    statefile: Path = Path("/tmp/minecraft-afk.state")

    @classmethod
    def from_entrypoint(cls, entrypoint: str | Path) -> "ProjectPaths":
        root = Path(entrypoint).resolve().parent
        return cls(root=root, scripts=root / "scripts")

    @classmethod
    def default(cls) -> "ProjectPaths":
        package_dir = Path(__file__).resolve().parent
        root = package_dir.parent
        return cls(root=root, scripts=root / "scripts")
