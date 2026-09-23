"""Cálculos para la Stone Farm con clic izquierdo mantenido.

La GUI usa este módulo para estimar cuánto tiempo puede minar antes de que el
pico alcance una durabilidad mínima configurada. El cálculo usa Stone en
Minecraft Java Edition y modela Unbreaking como un valor esperado, no como una
garantía exacta.
"""

from __future__ import annotations

from dataclasses import dataclass
import math


BLOCK_NAME = "Stone"
BLOCK_HARDNESS = 1.5
TICK_SECONDS = 0.05
CONTINUOUS_BREAK_DELAY_SECONDS = 0.30
DEFAULT_CALIBRATED_SECONDS_PER_DURABILITY = 28.0 / 19.0


@dataclass(frozen=True)
class Pickaxe:
    key: str
    label: str
    speed: float
    max_durability: int


PICKAXES: tuple[Pickaxe, ...] = (
    Pickaxe("wood", "Pico de madera", 2.0, 59),
    Pickaxe("stone", "Pico de piedra", 4.0, 131),
    Pickaxe("iron", "Pico de hierro", 6.0, 250),
    Pickaxe("gold", "Pico de oro", 12.0, 32),
    Pickaxe("diamond", "Pico de diamante", 8.0, 1561),
    Pickaxe("netherite", "Pico de netherita", 9.0, 2031),
)
PICKAXE_BY_KEY = {item.key: item for item in PICKAXES}


@dataclass(frozen=True)
class MiningPlan:
    final_speed: float
    progress_per_tick: float
    break_ticks: int
    break_seconds: float
    instant_break: bool
    continuous_cycle_seconds: float
    durability_to_spend: int
    expected_blocks: int
    estimated_duration_seconds: float
    expected_durability_loss_per_block: float
    calculation_method: str
    calibrated_seconds_per_durability: float
    seconds_per_durability: float


def calculate_stone_plan(
    pickaxe_key: str,
    current_durability: int,
    minimum_durability: int,
    efficiency: int = 0,
    unbreaking: int = 0,
    haste: int = 0,
    calculation_method: str = "theoretical",
    calibrated_seconds_per_durability: float = DEFAULT_CALIBRATED_SECONDS_PER_DURABILITY,
) -> MiningPlan:
    """Calcula el plan estimado de minado continuo de Stone.

    Para herramientas, Unbreaking nivel N consume en promedio un punto de
    durabilidad cada N+1 usos. Por ello, el número esperado de bloques se
    multiplica por N+1. Como el encantamiento es aleatorio, el resultado es
    una estimación estadística.
    """

    try:
        pickaxe = PICKAXE_BY_KEY[pickaxe_key]
    except KeyError as exc:
        raise ValueError(f"Pico desconocido: {pickaxe_key}") from exc

    if not 0 <= efficiency <= 5:
        raise ValueError("Efficiency debe estar entre 0 y 5")
    if not 0 <= unbreaking <= 3:
        raise ValueError("Unbreaking debe estar entre 0 y 3")
    if not 0 <= haste <= 2:
        raise ValueError("Haste debe estar entre 0 y 2")
    if calculation_method not in {"theoretical", "calibrated"}:
        raise ValueError("Método de cálculo desconocido")
    if calibrated_seconds_per_durability <= 0:
        raise ValueError("La calibración debe ser mayor que 0 segundos")
    if current_durability < 1:
        raise ValueError("La durabilidad actual debe ser al menos 1")
    if current_durability > pickaxe.max_durability:
        raise ValueError(
            f"La durabilidad máxima de {pickaxe.label} es {pickaxe.max_durability}"
        )
    if minimum_durability < 0:
        raise ValueError("La durabilidad mínima no puede ser negativa")
    if minimum_durability >= current_durability:
        raise ValueError("La durabilidad mínima debe ser menor que la actual")

    speed = pickaxe.speed
    if efficiency > 0:
        speed += efficiency * efficiency + 1
    speed *= 1.0 + 0.2 * haste

    progress = speed / BLOCK_HARDNESS / 30.0
    if progress <= 0:
        raise ValueError("La velocidad calculada no permite romper Stone")

    # En Java, damage > 1 implica instant mining y evita el retraso de 0.30 s.
    instant_break = progress > 1.0
    if instant_break:
        break_ticks = 1
        break_seconds = TICK_SECONDS
        cycle_seconds = TICK_SECONDS
    else:
        break_ticks = math.ceil(1.0 / progress)
        break_seconds = break_ticks * TICK_SECONDS
        cycle_seconds = break_seconds + CONTINUOUS_BREAK_DELAY_SECONDS

    durability_to_spend = current_durability - minimum_durability
    expected_blocks = durability_to_spend * (unbreaking + 1)
    theoretical_seconds_per_durability = (unbreaking + 1) * cycle_seconds
    if calculation_method == "calibrated":
        # La calibración se obtiene de una prueba real de la granja y por ello
        # ya incluye el tiempo muerto del generador agua/lava, latencia y la
        # configuración del pico usada durante esa prueba.
        seconds_per_durability = calibrated_seconds_per_durability
    else:
        seconds_per_durability = theoretical_seconds_per_durability

    estimated_duration_seconds = durability_to_spend * seconds_per_durability

    return MiningPlan(
        final_speed=speed,
        progress_per_tick=progress,
        break_ticks=break_ticks,
        break_seconds=break_seconds,
        instant_break=instant_break,
        continuous_cycle_seconds=cycle_seconds,
        durability_to_spend=durability_to_spend,
        expected_blocks=expected_blocks,
        estimated_duration_seconds=estimated_duration_seconds,
        expected_durability_loss_per_block=1.0 / (unbreaking + 1),
        calculation_method=calculation_method,
        calibrated_seconds_per_durability=calibrated_seconds_per_durability,
        seconds_per_durability=seconds_per_durability,
    )


def calculate_calibration(
    durability_before: int, durability_after: int, test_seconds: float
) -> float:
    """Devuelve segundos reales por punto de durabilidad consumido."""

    if durability_before <= durability_after:
        raise ValueError("La durabilidad inicial debe ser mayor que la final")
    if durability_after < 0:
        raise ValueError("La durabilidad final no puede ser negativa")
    if test_seconds <= 0:
        raise ValueError("La duración de la prueba debe ser mayor que 0")
    spent = durability_before - durability_after
    return test_seconds / spent


def format_duration(seconds: float) -> str:
    """Convierte segundos a un texto compacto HH h MM min SS s."""

    total = max(0, int(round(seconds)))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d} h {minutes:02d} min {secs:02d} s"
    if minutes:
        return f"{minutes:02d} min {secs:02d} s"
    return f"{secs:02d} s"
