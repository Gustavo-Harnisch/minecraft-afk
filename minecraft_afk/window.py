"""Ventana principal de Minecraft AFK."""

from __future__ import annotations


import os
import threading
import time

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk

from .config import ProjectPaths
from .i18n import _, set_language, SUPPORTED_LANGUAGES
from .mining import (
    PICKAXES,
    PICKAXE_BY_KEY,
    calculate_calibration,
    calculate_stone_plan,
    format_duration,
)
from .scripts import BashScriptRunner, CommandResult
from .settings import SettingsStore


class MinecraftAfkWindow(Gtk.Window):
    """Panel gráfico principal para controlar las automatizaciones AFK."""

    STATUS_REFRESH_MS = 500

    def __init__(
        self,
        paths: ProjectPaths | None = None,
        script_runner: BashScriptRunner | None = None,
    ) -> None:
        super().__init__(title="Minecraft AFK")
        self.set_default_size(1180, 720)
        self.set_size_request(920, 620)
        self.set_position(Gtk.WindowPosition.CENTER)

        self.script_runner = script_runner or BashScriptRunner(paths)
        self.paths = self.script_runner.paths
        self.settings = SettingsStore()
        self.language = set_language(str(self.settings.data.get("language", "auto")))
        self.script_runner.language = self.language
        self._status_timer_id: int | None = None
        self._status_fields: dict[str, Gtk.Label] = {}
        self._syncing_stone = False
        self._loading_settings = False
        self._last_runtime_state: dict[str, str] = {}
        self._stop_requested = False
        self._stone_completion_visible = False
        self._last_completion_was_calibration = False

        self._install_css()
        self._build_ui()
        self._load_controls_from_settings()
        self._update_stone_estimate()
        self._refresh_runtime_status()
        self._status_timer_id = GLib.timeout_add(
            self.STATUS_REFRESH_MS, self._refresh_runtime_status
        )
        self.connect("destroy", self._on_destroy)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        root.get_style_context().add_class("app-root")
        self.add(root)

        # La ventana usa únicamente la barra de título nativa del sistema.
        # Conservamos este label fuera del árbol visual para no acoplar la lógica
        # de estado a una cabecera personalizada.
        self.global_status_label = Gtk.Label(label=_("Detenido"))

        self.notebook = Gtk.Notebook()
        self.notebook.set_scrollable(True)
        self.notebook.get_style_context().add_class("main-notebook")
        root.pack_start(self.notebook, True, True, 0)

        self.notebook.append_page(self._build_mob_page(), Gtk.Label(label="Mob Farm"))
        self.notebook.append_page(self._build_stone_page(), Gtk.Label(label="Stone Farm"))
        self.notebook.append_page(self._build_status_page(), Gtk.Label(label=_("Estado")))
        self.notebook.append_page(self._build_logs_page(), Gtk.Label(label=_("Logs")))
        self.notebook.append_page(self._build_settings_page(), Gtk.Label(label=_("Ajustes")))

    def _build_header(self) -> Gtk.Widget:
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        header.set_border_width(16)
        header.get_style_context().add_class("header-bar-custom")

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title = Gtk.Label(label="Minecraft AFK")
        title.set_xalign(0)
        title.get_style_context().add_class("app-title")
        subtitle = Gtk.Label(label=_("Control gráfico de farms para Linux"))
        subtitle.set_xalign(0)
        subtitle.get_style_context().add_class("muted")
        title_box.pack_start(title, False, False, 0)
        title_box.pack_start(subtitle, False, False, 0)
        header.pack_start(title_box, True, True, 0)

        self.global_status_label = Gtk.Label(label=_("Detenido"))
        self.global_status_label.get_style_context().add_class("status-pill")
        header.pack_start(self.global_status_label, False, False, 0)

        emergency = Gtk.Button(label=_("DETENER TODO"))
        emergency.get_style_context().add_class("danger-button")
        emergency.connect("clicked", self._on_emergency_stop)
        header.pack_start(emergency, False, False, 0)
        return header

    def _build_mob_page(self) -> Gtk.Widget:
        page = self._page_container()
        page.pack_start(
            self._section_heading(
                "Mob Farm",
                _("Realiza un clic izquierdo automático con el intervalo que definas."),
            ),
            False,
            False,
            0,
        )

        card = self._card()
        grid = self._form_grid()
        card.add(grid)

        self.mob_interval = self._spin(2.0, 0.01, 3600.0, 0.05, digits=2)
        self.mob_interval.set_tooltip_text(_("Segundos entre cada ataque"))
        self._grid_row(grid, 0, _("Intervalo entre ataques"), self.mob_interval, _("segundos"))

        self.mob_state_label = Gtk.Label(label=_("Detenido"))
        self.mob_state_label.set_xalign(0)
        self._grid_row(grid, 1, _("Estado"), self.mob_state_label)
        page.pack_start(card, False, False, 0)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.mob_start_button = Gtk.Button(label=_("INICIAR MOB FARM"))
        self.mob_start_button.get_style_context().add_class("primary-button")
        self.mob_start_button.connect("clicked", self._on_start_mob)
        buttons.pack_start(self.mob_start_button, True, True, 0)

        self.mob_stop_button = Gtk.Button(label=_("DETENER"))
        self.mob_stop_button.connect("clicked", self._on_emergency_stop)
        buttons.pack_start(self.mob_stop_button, False, False, 0)
        page.pack_start(buttons, False, False, 0)

        self.mob_interval.connect("value-changed", self._on_mob_config_changed)
        return page

    def _build_stone_page(self) -> Gtk.Widget:
        page = self._page_container()
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.add_with_viewport(page)
        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        page.pack_start(body, True, True, 0)

        config_card = self._card()
        config_card.set_hexpand(True)
        config_card.set_size_request(470, -1)
        config_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        config_box.set_border_width(18)
        config_card.add(config_box)

        config_title = Gtk.Label(label=_("Configuración de la farm"))
        config_title.set_xalign(0)
        config_title.get_style_context().add_class("card-title")
        config_box.pack_start(config_title, False, False, 0)

        config_separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        config_box.pack_start(config_separator, False, False, 12)

        grid = self._form_grid()
        grid.set_border_width(0)
        config_box.pack_start(grid, True, True, 0)
        body.pack_start(config_card, True, True, 0)

        block = Gtk.Label(label=_("Cobblestone / Stone"))
        block.set_xalign(0)
        self._grid_row(grid, 0, _("Bloque"), block)

        self.calculation_method_combo = Gtk.ComboBoxText()
        self.calculation_method_combo.append("calibrated", _("Calibrado · Cobblestone Farm"))
        self.calculation_method_combo.append("theoretical", _("Teórico · minería continua"))
        self._grid_row(grid, 1, _("Método de cálculo"), self.calculation_method_combo)

        self.pickaxe_combo = Gtk.ComboBoxText()
        for pickaxe in PICKAXES:
            self.pickaxe_combo.append(pickaxe.key, _(pickaxe.label))
        self._grid_row(grid, 2, _("Pico"), self.pickaxe_combo)

        self.current_durability_spin = self._spin(1561, 1, 2031, 1, digits=0)
        self.current_durability_spin.set_tooltip_text(
            _("Durabilidad que muestra actualmente el pico en Minecraft")
        )
        self._grid_row(grid, 3, _("Durabilidad actual"), self.current_durability_spin)

        self.minimum_durability_spin = self._spin(100, 0, 2030, 1, digits=0)
        self.minimum_durability_spin.set_tooltip_text(
            _("Durabilidad objetivo en la que quieres detener la farm")
        )
        self._grid_row(grid, 4, _("Durabilidad mínima"), self.minimum_durability_spin)

        self.efficiency_spin = self._spin(0, 0, 5, 1, digits=0)
        self._grid_row(grid, 5, "Efficiency", self.efficiency_spin)

        self.unbreaking_spin = self._spin(0, 0, 3, 1, digits=0)
        self._grid_row(grid, 6, "Unbreaking", self.unbreaking_spin)

        self.haste_spin = self._spin(0, 0, 2, 1, digits=0)
        self._grid_row(grid, 7, "Haste", self.haste_spin)

        self.calibrated_seconds_spin = self._spin(1.474, 0.001, 60.0, 0.001, digits=3)
        self.calibrated_seconds_spin.set_tooltip_text(
            _("Segundos reales que tu granja tarda en consumir 1 punto de durabilidad")
        )
        self._grid_row(grid, 8, _("Segundos / durabilidad"), self.calibrated_seconds_spin, "s")

        self.calibration_mode_switch = Gtk.Switch()
        self.calibration_mode_switch.set_halign(Gtk.Align.START)
        self.calibration_mode_switch.set_valign(Gtk.Align.CENTER)
        self.calibration_mode_switch.set_hexpand(False)
        self.calibration_mode_switch.get_style_context().add_class("calibration-toggle")
        self.calibration_mode_switch.set_tooltip_text(
            _("Activa una prueba controlada: 20 s para prepararte y después mantiene el clic durante el tiempo indicado")
        )

        calibration_toggle_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        calibration_toggle_box.set_hexpand(True)
        calibration_toggle_box.set_halign(Gtk.Align.FILL)
        calibration_toggle_box.pack_start(self.calibration_mode_switch, False, False, 0)
        self.calibration_mode_state_label = Gtk.Label(label=_("Desactivado"))
        self.calibration_mode_state_label.set_xalign(0)
        self.calibration_mode_state_label.get_style_context().add_class("toggle-state")
        calibration_toggle_box.pack_start(
            self.calibration_mode_state_label, False, False, 0
        )
        self._grid_row(grid, 9, _("Modo calibración"), calibration_toggle_box)

        self.calibration_seconds_spin = self._spin(30.0, 1.0, 60.0, 1.0, digits=0)
        self.calibration_seconds_spin.set_tooltip_text(
            _("Tiempo exacto que durará la prueba de calibración. Máximo: 60 segundos.")
        )
        self._grid_row(grid, 10, _("Tiempo de calibración"), self.calibration_seconds_spin, "s")

        self.calibration_before_spin = self._spin(962, 1, 5000, 1, digits=0)
        self.calibration_before_spin.set_tooltip_text(
            _("Durabilidad del pico justo antes de iniciar la prueba")
        )
        self._grid_row(grid, 11, _("Prueba: durabilidad antes"), self.calibration_before_spin)

        self.calibration_after_spin = self._spin(943, 0, 4999, 1, digits=0)
        self.calibration_after_spin.set_tooltip_text(
            _("Durabilidad del pico al terminar la prueba")
        )
        self._grid_row(grid, 12, _("Prueba: durabilidad después"), self.calibration_after_spin)

        self.apply_calibration_button = Gtk.Button(label=_("CALCULAR Y GUARDAR CALIBRACIÓN"))
        self.apply_calibration_button.set_tooltip_text(
            _("Usa la durabilidad antes/después y el tiempo de prueba para calcular segundos por durabilidad")
        )
        self._grid_row(grid, 13, _("Resultado"), self.apply_calibration_button)

        self.auto_stop_check = Gtk.CheckButton(
            label=_("Detener automáticamente al llegar al tiempo estimado")
        )
        self._grid_row(grid, 14, "Auto-stop", self.auto_stop_check)

        info_card = self._card()
        info_card.set_hexpand(True)
        info_card.set_size_request(540, -1)
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        info_box.set_border_width(16)
        info_card.add(info_box)

        info_title = Gtk.Label(label=_("Temporizador de durabilidad / calibración"))
        info_title.set_xalign(0)
        info_title.get_style_context().add_class("card-title")
        info_box.pack_start(info_title, False, False, 0)

        # Panel principal de cuenta regresiva. Primero muestra los 20 s de
        # preparación y después reutiliza el mismo espacio para el tiempo
        # restante hasta alcanzar la durabilidad objetivo.
        self.stone_phase_label = Gtk.Label(label=_("LISTO"))
        self.stone_phase_label.set_xalign(0)
        self.stone_phase_label.get_style_context().add_class("timer-phase")
        info_box.pack_start(self.stone_phase_label, False, False, 0)

        self.stone_countdown_label = Gtk.Label(label="--:--")
        self.stone_countdown_label.set_xalign(0)
        self.stone_countdown_label.get_style_context().add_class("countdown-value")
        info_box.pack_start(self.stone_countdown_label, False, False, 0)

        self.stone_countdown_caption = Gtk.Label(label=_("Listo para iniciar"))
        self.stone_countdown_caption.set_xalign(0)
        self.stone_countdown_caption.set_line_wrap(True)
        self.stone_countdown_caption.get_style_context().add_class("muted")
        info_box.pack_start(self.stone_countdown_caption, False, False, 0)

        self.stone_progress = Gtk.ProgressBar()
        self.stone_progress.set_show_text(True)
        self.stone_progress.set_fraction(0.0)
        self.stone_progress.set_text(_("Esperando"))
        self.stone_progress.get_style_context().add_class("stone-progress")
        info_box.pack_start(self.stone_progress, False, False, 2)

        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        info_box.pack_start(separator, False, False, 6)

        summary_title = Gtk.Label(label=_("Resumen"))
        summary_title.set_xalign(0)
        summary_title.get_style_context().add_class("summary-title")
        info_box.pack_start(summary_title, False, False, 0)

        summary_separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        info_box.pack_start(summary_separator, False, False, 4)

        self.stone_pickaxe_info = self._info_value(info_box, _("Pico"))
        self.stone_max_durability_info = self._info_value(info_box, _("Durabilidad máxima"))
        self.stone_spend_info = self._info_value(info_box, _("Durabilidad a consumir"))
        self.stone_blocks_info = self._info_value(info_box, _("Bloques estimados"))
        self.stone_method_info = self._info_value(info_box, _("Método de cálculo"))
        self.stone_cycle_info = self._info_value(info_box, _("Base temporal usada"))
        self.stone_duration_info = self._info_value(info_box, _("Tiempo estimado hasta el objetivo"))
        self.stone_target_info = self._info_value(info_box, _("Durabilidad final estimada"))
        self.stone_live_timer_info = self._info_value(info_box, _("Temporizador activo"))

        warning_frame = Gtk.Frame()
        warning_frame.set_shadow_type(Gtk.ShadowType.NONE)
        warning_frame.get_style_context().add_class("info-callout")
        self.stone_warning_label = Gtk.Label(label="")
        self.stone_warning_label.set_xalign(0)
        self.stone_warning_label.set_line_wrap(True)
        self.stone_warning_label.set_margin_start(12)
        self.stone_warning_label.set_margin_end(12)
        self.stone_warning_label.set_margin_top(10)
        self.stone_warning_label.set_margin_bottom(10)
        self.stone_warning_label.get_style_context().add_class("muted")
        warning_frame.add(self.stone_warning_label)
        info_box.pack_end(warning_frame, False, False, 0)

        body.pack_start(info_card, True, True, 0)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.stone_start_button = Gtk.Button(label=_("INICIAR MINADO CONTINUO"))
        self.stone_start_button.get_style_context().add_class("primary-button")
        self.stone_start_button.connect("clicked", self._on_start_stone)
        buttons.pack_start(self.stone_start_button, True, True, 0)

        self.calibration_start_button = Gtk.Button(label=_("INICIAR CALIBRACIÓN"))
        self.calibration_start_button.get_style_context().add_class("calibration-button")
        self.calibration_start_button.set_tooltip_text(
            _("Hace 20 s de preparación y luego mantiene el clic durante el tiempo de calibración")
        )
        self.calibration_start_button.connect("clicked", self._on_start_calibration)
        buttons.pack_start(self.calibration_start_button, True, True, 0)

        self.stone_stop_button = Gtk.Button(label=_("DETENER Y LIBERAR CLIC"))
        self.stone_stop_button.get_style_context().add_class("secondary-button")
        self.stone_stop_button.connect("clicked", self._on_emergency_stop)
        buttons.pack_start(self.stone_stop_button, False, False, 0)
        page.pack_start(buttons, False, False, 0)

        self.calculation_method_combo.connect("changed", self._on_stone_config_changed)
        self.pickaxe_combo.connect("changed", self._on_stone_config_changed)
        self.current_durability_spin.connect("value-changed", self._on_stone_config_changed)
        self.minimum_durability_spin.connect("value-changed", self._on_stone_config_changed)
        self.efficiency_spin.connect("value-changed", self._on_stone_config_changed)
        self.unbreaking_spin.connect("value-changed", self._on_stone_config_changed)
        self.haste_spin.connect("value-changed", self._on_stone_config_changed)
        self.calibrated_seconds_spin.connect("value-changed", self._on_stone_config_changed)
        self.calibration_mode_switch.connect("notify::active", self._on_calibration_mode_toggled)
        self.calibration_before_spin.connect("value-changed", self._on_stone_config_changed)
        self.calibration_after_spin.connect("value-changed", self._on_stone_config_changed)
        self.calibration_seconds_spin.connect("value-changed", self._on_stone_config_changed)
        self.apply_calibration_button.connect("clicked", self._on_apply_calibration)
        self.auto_stop_check.connect("toggled", self._on_stone_config_changed)
        return scroller

    def _build_status_page(self) -> Gtk.Widget:
        page = self._page_container()
        page.pack_start(
            self._section_heading(
                _("Estado"),
                _("Información del proceso AFK que está ejecutándose actualmente."),
            ),
            False,
            False,
            0,
        )

        card = self._card()
        grid = self._form_grid()
        card.add(grid)
        fields = (
            ("running", _("Estado general")),
            ("mode", _("Modo")),
            ("pid", "PID"),
            ("interval", _("Intervalo Mob Farm")),
            ("pickaxe", _("Pico")),
            ("durability", _("Durabilidad objetivo")),
            ("enchantments", _("Encantamientos / efectos")),
            ("expected_blocks", _("Bloques estimados")),
            ("timer", _("Temporizador restante")),
        )
        for row, (key, caption) in enumerate(fields):
            value = Gtk.Label(label="—")
            value.set_xalign(0)
            value.set_selectable(True)
            self._status_fields[key] = value
            self._grid_row(grid, row, caption, value)
        page.pack_start(card, False, False, 0)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        refresh = Gtk.Button(label=_("Actualizar"))
        refresh.connect("clicked", lambda *_: self._refresh_runtime_status())
        controls.pack_start(refresh, False, False, 0)
        stop = Gtk.Button(label=_("DETENER TODO"))
        stop.get_style_context().add_class("danger-button")
        stop.connect("clicked", self._on_emergency_stop)
        controls.pack_end(stop, False, False, 0)
        page.pack_start(controls, False, False, 0)
        return page

    def _build_logs_page(self) -> Gtk.Widget:
        page = self._page_container()
        page.pack_start(
            self._section_heading(
                _("Logs"),
                _("Aquí se muestra la salida de los scripts. No necesitas escribir comandos."),
            ),
            False,
            False,
            0,
        )

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.log_view = Gtk.TextView()
        self.log_view.set_editable(False)
        self.log_view.set_cursor_visible(False)
        self.log_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.log_view.set_monospace(True)
        self.log_buffer = self.log_view.get_buffer()
        scroll.add(self.log_view)
        page.pack_start(scroll, True, True, 0)

        clear = Gtk.Button(label=_("Limpiar logs"))
        clear.connect("clicked", lambda *_: self.log_buffer.set_text(""))
        page.pack_start(clear, False, False, 0)
        return page

    def _build_settings_page(self) -> Gtk.Widget:
        page = self._page_container()
        page.pack_start(
            self._section_heading(
                _("Ajustes"),
                _("La configuración de la GUI se guarda automáticamente."),
            ),
            False,
            False,
            0,
        )

        card = self._card()
        grid = self._form_grid()
        card.add(grid)

        config_path = Gtk.Label(label=str(self.settings.path))
        config_path.set_xalign(0)
        config_path.set_selectable(True)
        config_path.set_line_wrap(True)
        self._grid_row(grid, 0, _("Archivo de configuración"), config_path)

        scripts_path = Gtk.Label(label=str(self.paths.scripts))
        scripts_path.set_xalign(0)
        scripts_path.set_selectable(True)
        scripts_path.set_line_wrap(True)
        self._grid_row(grid, 1, _("Scripts Bash"), scripts_path)

        runtime = Gtk.Label(label="/tmp/minecraft-afk.pid  ·  /tmp/minecraft-afk.state")
        runtime.set_xalign(0)
        runtime.set_selectable(True)
        self._grid_row(grid, 2, _("Estado de ejecución"), runtime)

        note = Gtk.Label(
            label=(
                _("Requiere xdotool y una sesión X11. En Linux Mint puedes instalar "
                "xdotool con: sudo apt install xdotool")
            )
        )
        note.set_xalign(0)
        note.set_line_wrap(True)
        note.get_style_context().add_class("muted")
        self._grid_row(grid, 3, _("Compatibilidad"), note)

        self.language_combo = Gtk.ComboBoxText()
        self.language_combo.append("auto", _("Automático (idioma del sistema)"))
        self.language_combo.append("es", "Español")
        self.language_combo.append("en", "English")
        language = str(self.settings.data.get("language", "auto"))
        self.language_combo.set_active_id(language if language in SUPPORTED_LANGUAGES else "auto")
        self.language_combo.connect("changed", self._on_language_changed)
        self._grid_row(grid, 4, _("Idioma"), self.language_combo)
        self.language_notice = Gtk.Label(label="")
        self.language_notice.set_xalign(0)
        self.language_notice.set_line_wrap(True)
        self._grid_row(grid, 5, "", self.language_notice)
        page.pack_start(card, False, False, 0)
        return page

    def _on_language_changed(self, _combo: Gtk.ComboBoxText) -> None:
        if self._loading_settings:
            return
        language = self.language_combo.get_active_id() or "auto"
        previous = str(self.settings.data.get("language", "auto"))
        self.settings.data["language"] = language
        if self._save_settings_safely():
            self.language_notice.set_text(_("Reinicia la aplicación para aplicar el idioma."))
        else:
            self.settings.data["language"] = previous
            self._loading_settings = True
            try:
                self.language_combo.set_active_id(previous if previous in SUPPORTED_LANGUAGES else "auto")
            finally:
                self._loading_settings = False
            self.language_notice.set_text(_("No se pudo guardar el idioma. Revisa los logs."))

    # --------------------------------------------------------------- Helpers
    def _page_container(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_border_width(16)
        return box

    def _section_heading(self, title: str, subtitle: str) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        heading = Gtk.Label(label=title)
        heading.set_xalign(0)
        heading.get_style_context().add_class("section-title")
        detail = Gtk.Label(label=subtitle)
        detail.set_xalign(0)
        detail.set_line_wrap(True)
        detail.get_style_context().add_class("muted")
        box.pack_start(heading, False, False, 0)
        box.pack_start(detail, False, False, 0)
        return box

    def _card(self) -> Gtk.Frame:
        frame = Gtk.Frame()
        frame.set_shadow_type(Gtk.ShadowType.NONE)
        frame.set_border_width(0)
        frame.get_style_context().add_class("card")
        return frame

    def _form_grid(self) -> Gtk.Grid:
        grid = Gtk.Grid()
        grid.set_row_spacing(8)
        grid.set_column_spacing(14)
        grid.set_border_width(16)
        return grid

    def _grid_row(
        self,
        grid: Gtk.Grid,
        row: int,
        caption: str,
        widget: Gtk.Widget,
        suffix: str | None = None,
    ) -> None:
        label = Gtk.Label(label=caption)
        label.set_xalign(0)
        label.get_style_context().add_class("form-label")
        grid.attach(label, 0, row, 1, 1)
        widget.set_hexpand(True)
        grid.attach(widget, 1, row, 1, 1)
        if suffix:
            unit = Gtk.Label(label=suffix)
            unit.set_xalign(0)
            unit.get_style_context().add_class("muted")
            grid.attach(unit, 2, row, 1, 1)

    def _spin(
        self,
        value: float,
        lower: float,
        upper: float,
        step: float,
        digits: int,
    ) -> Gtk.SpinButton:
        adjustment = Gtk.Adjustment(
            value=value,
            lower=lower,
            upper=upper,
            step_increment=step,
            page_increment=max(step * 10, 1),
            page_size=0,
        )
        spin = Gtk.SpinButton(adjustment=adjustment, climb_rate=step, digits=digits)
        spin.set_numeric(True)
        return spin

    def _info_value(self, parent: Gtk.Box, caption: str) -> Gtk.Label:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        label = Gtk.Label(label=caption)
        label.set_xalign(0)
        label.get_style_context().add_class("muted")
        value = Gtk.Label(label="—")
        value.set_xalign(0)
        value.set_selectable(True)
        value.set_line_wrap(True)
        value.get_style_context().add_class("info-value")
        box.pack_start(label, False, False, 0)
        box.pack_start(value, False, False, 0)
        parent.pack_start(box, False, False, 0)
        return value

    # ---------------------------------------------------------- Configuration
    def _load_controls_from_settings(self) -> None:
        self._loading_settings = True
        try:
            mob = self.settings.data["mob_farm"]
            stone = self.settings.data["stone_farm"]

            self.mob_interval.set_value(float(mob.get("interval", 2.0)))

            pickaxe_key = str(stone.get("pickaxe", "diamond"))
            if pickaxe_key not in PICKAXE_BY_KEY:
                pickaxe_key = "diamond"
            self.pickaxe_combo.set_active_id(pickaxe_key)
            pickaxe = PICKAXE_BY_KEY[pickaxe_key]

            current = int(stone.get("current_durability", pickaxe.max_durability))
            current = max(1, min(current, pickaxe.max_durability))
            minimum = int(stone.get("minimum_durability", min(100, current - 1)))
            minimum = max(0, min(minimum, current - 1))

            method = str(stone.get("calculation_method", "calibrated"))
            if method not in {"calibrated", "theoretical"}:
                method = "calibrated"
            self.calculation_method_combo.set_active_id(method)

            self.current_durability_spin.set_value(current)
            self.minimum_durability_spin.set_value(minimum)
            self.efficiency_spin.set_value(int(stone.get("efficiency", 0)))
            self.unbreaking_spin.set_value(int(stone.get("unbreaking", 0)))
            self.haste_spin.set_value(int(stone.get("haste", 0)))
            self.calibrated_seconds_spin.set_value(float(stone.get("calibrated_seconds_per_durability", 1.474)))
            self.calibration_mode_switch.set_active(bool(stone.get("calibration_mode", False)))
            self.calibration_before_spin.set_value(int(stone.get("calibration_before", 962)))
            self.calibration_after_spin.set_value(int(stone.get("calibration_after", 943)))
            self.calibration_seconds_spin.set_value(min(60.0, max(1.0, float(stone.get("calibration_seconds", 30.0)))))
            self.auto_stop_check.set_active(bool(stone.get("auto_stop", True)))
            self._sync_durability_limits()
            self._sync_calibration_mode_ui()
        finally:
            self._loading_settings = False

    def _on_mob_config_changed(self, *_args: object) -> None:
        if self._loading_settings:
            return
        self.settings.data["mob_farm"]["interval"] = round(
            self.mob_interval.get_value(), 2
        )
        self._save_settings_safely()

    def _sync_durability_limits(self) -> None:
        if self._syncing_stone:
            return
        self._syncing_stone = True
        try:
            key = self.pickaxe_combo.get_active_id() or "diamond"
            pickaxe = PICKAXE_BY_KEY.get(key, PICKAXE_BY_KEY["diamond"])

            current_adjustment = self.current_durability_spin.get_adjustment()
            current_adjustment.set_upper(pickaxe.max_durability)
            if self.current_durability_spin.get_value_as_int() > pickaxe.max_durability:
                self.current_durability_spin.set_value(pickaxe.max_durability)

            current = max(1, self.current_durability_spin.get_value_as_int())
            minimum_adjustment = self.minimum_durability_spin.get_adjustment()
            minimum_adjustment.set_upper(max(0, current - 1))
            if self.minimum_durability_spin.get_value_as_int() >= current:
                self.minimum_durability_spin.set_value(max(0, current - 1))
        finally:
            self._syncing_stone = False

    def _stone_config(self) -> dict[str, object]:
        return {
            "pickaxe": self.pickaxe_combo.get_active_id() or "diamond",
            "current_durability": self.current_durability_spin.get_value_as_int(),
            "minimum_durability": self.minimum_durability_spin.get_value_as_int(),
            "efficiency": self.efficiency_spin.get_value_as_int(),
            "unbreaking": self.unbreaking_spin.get_value_as_int(),
            "haste": self.haste_spin.get_value_as_int(),
            "calculation_method": self.calculation_method_combo.get_active_id() or "calibrated",
            "calibrated_seconds_per_durability": round(self.calibrated_seconds_spin.get_value(), 3),
            "calibration_mode": self.calibration_mode_switch.get_active(),
            "calibration_before": self.calibration_before_spin.get_value_as_int(),
            "calibration_after": self.calibration_after_spin.get_value_as_int(),
            "calibration_seconds": round(self.calibration_seconds_spin.get_value(), 1),
            "auto_stop": self.auto_stop_check.get_active(),
        }

    def _sync_calibration_mode_ui(self) -> None:
        active = self.calibration_mode_switch.get_active()
        self.calibration_mode_state_label.set_text(
            _("Activado") if active else _("Desactivado")
        )
        state_context = self.calibration_mode_state_label.get_style_context()
        if active:
            state_context.add_class("active")
        else:
            state_context.remove_class("active")
        self.calibration_seconds_spin.set_sensitive(active)
        self.calibration_before_spin.set_sensitive(active)
        self.calibration_after_spin.set_sensitive(active)
        self.apply_calibration_button.set_sensitive(active)
        self.calibration_start_button.set_sensitive(active)
        self.stone_start_button.set_sensitive(not active)

        if active and not self._loading_settings:
            current = self.current_durability_spin.get_value_as_int()
            self.calibration_before_spin.set_value(current)
            after = self.calibration_after_spin.get_value_as_int()
            if after >= current:
                self.calibration_after_spin.set_value(max(0, current - 1))

    def _on_calibration_mode_toggled(self, *_args: object) -> None:
        self._sync_calibration_mode_ui()
        self._on_stone_config_changed()

    def _on_stone_config_changed(self, *_args: object) -> None:
        if self._syncing_stone:
            return
        self._sync_durability_limits()
        if not self._loading_settings:
            self.settings.data["stone_farm"] = self._stone_config()
            self._save_settings_safely()
        self._update_stone_estimate()

    def _on_apply_calibration(self, _button: Gtk.Button) -> None:
        try:
            seconds_per_durability = calculate_calibration(
                self.calibration_before_spin.get_value_as_int(),
                self.calibration_after_spin.get_value_as_int(),
                self.calibration_seconds_spin.get_value(),
            )
        except ValueError as error:
            message = _("Calibración inválida: {error}").format(error=error)
            self._append_log(message)
            self.stone_warning_label.set_text(message)
            return

        self._syncing_stone = True
        try:
            self.calibrated_seconds_spin.set_value(seconds_per_durability)
            self.calculation_method_combo.set_active_id("calibrated")
        finally:
            self._syncing_stone = False

        self.settings.data["stone_farm"] = self._stone_config()
        self._save_settings_safely()
        self._update_stone_estimate()
        self._append_log(_(
            "Calibración guardada | Segundos/durabilidad: {rate:.3f} s | "
            "Prueba: {before} → {after} en {seconds:.0f} s"
        ).format(rate=seconds_per_durability,
                 before=self.calibration_before_spin.get_value_as_int(),
                 after=self.calibration_after_spin.get_value_as_int(),
                 seconds=self.calibration_seconds_spin.get_value()))

    def _save_settings_safely(self) -> bool:
        try:
            self.settings.save()
            return True
        except OSError as error:
            self._append_log(_("No se pudo guardar la configuración: {error}").format(error=error))
            return False

    def _update_stone_estimate(self) -> None:
        config = self._stone_config()
        try:
            result = calculate_stone_plan(
                pickaxe_key=str(config["pickaxe"]),
                current_durability=int(config["current_durability"]),
                minimum_durability=int(config["minimum_durability"]),
                efficiency=int(config["efficiency"]),
                unbreaking=int(config["unbreaking"]),
                haste=int(config["haste"]),
                calculation_method=str(config["calculation_method"]),
                calibrated_seconds_per_durability=float(
                    config["calibrated_seconds_per_durability"]
                ),
            )
        except ValueError as error:
            self.stone_duration_info.set_text(str(error))
            return

        pickaxe = PICKAXE_BY_KEY[str(config["pickaxe"])]
        self.stone_pickaxe_info.set_text(_(pickaxe.label))
        self.stone_max_durability_info.set_text(str(pickaxe.max_durability))
        self.stone_spend_info.set_text(str(result.durability_to_spend))
        self.stone_blocks_info.set_text(f"≈ {result.expected_blocks}")
        if result.calculation_method == "calibrated":
            self.stone_method_info.set_text(_("Calibrado · datos reales de la farm"))
            self.stone_cycle_info.set_text(
                _("{seconds:.3f} s / punto de durabilidad").format(seconds=result.seconds_per_durability)
            )
        else:
            self.stone_method_info.set_text(_("Teórico · mecánica vanilla"))
            self.stone_cycle_info.set_text(
                _("≈ {seconds:.2f} s / bloque").format(seconds=result.continuous_cycle_seconds)
            )
        self.stone_duration_info.set_text(format_duration(result.estimated_duration_seconds))
        self.stone_target_info.set_text(str(config["minimum_durability"]))

        if result.calculation_method == "calibrated":
            warning = _(
                "Calibración activa: {seconds:.3f} s por punto de durabilidad. "
                "Este valor ya incorpora el tiempo muerto del generador agua/lava. "
                "Recalibra si cambias la farm, el pico, Efficiency, Unbreaking o Haste."
            ).format(seconds=result.seconds_per_durability)
            if int(config["unbreaking"]) > 0:
                warning += _(" Con Unbreaking seguirá existiendo variación aleatoria.")
            self.stone_warning_label.set_text(warning)
        elif int(config["unbreaking"]) > 0:
            self.stone_warning_label.set_text(
                _("Modo teórico: Unbreaking hace que el consumo sea aleatorio y este cálculo no "
                "incluye el tiempo real que tarda tu generador de agua/lava en crear el siguiente bloque.")
            )
        else:
            self.stone_warning_label.set_text(
                _("Modo teórico: calcula la minería vanilla, pero no mide el retraso real del generador de cobblestone.")
            )

    # -------------------------------------------------------------- Commands
    def _on_start_mob(self, _button: Gtk.Button) -> None:
        interval = f"{self.mob_interval.get_value():.2f}"
        self._on_mob_config_changed()
        self._run_script("mob-farm", "start", "--interval", interval)

    def _on_start_stone(self, _button: Gtk.Button) -> None:
        self._stop_requested = False
        self._stone_completion_visible = False

        # Feedback inmediato: no esperamos a que Bash escriba el state file para
        # mostrar que comenzó la preparación. En cuanto llega el estado real, el
        # refresco periódico reemplaza estos valores por la cuenta exacta.
        self.stone_phase_label.set_text(_("PREPARACIÓN"))
        self.stone_countdown_label.set_text("00:20")
        self.stone_countdown_caption.set_text(
            _("Prepárate: cambia a Minecraft y apunta al bloque que quieres minar.")
        )
        self.stone_progress.set_fraction(0.0)
        self.stone_progress.set_text(_("Preparación 0%"))
        self.stone_live_timer_info.set_text(_("Preparación · 00:20"))

        config = self._stone_config()
        try:
            plan = calculate_stone_plan(
                pickaxe_key=str(config["pickaxe"]),
                current_durability=int(config["current_durability"]),
                minimum_durability=int(config["minimum_durability"]),
                efficiency=int(config["efficiency"]),
                unbreaking=int(config["unbreaking"]),
                haste=int(config["haste"]),
                calculation_method=str(config["calculation_method"]),
                calibrated_seconds_per_durability=float(
                    config["calibrated_seconds_per_durability"]
                ),
            )
        except ValueError as error:
            self._append_log(_("Configuración inválida: {error}").format(error=error))
            return

        method_label = (
            _("Calibrado") if plan.calculation_method == "calibrated" else _("Teórico")
        )
        self._append_log(_(
            "Stone Farm | Método: {method} | Segundos/durabilidad: {rate:.3f} s | "
            "Durabilidad: {current} → {minimum} | Tiempo objetivo: {duration}"
        ).format(method=method_label, rate=plan.seconds_per_durability,
                 current=config["current_durability"], minimum=config["minimum_durability"],
                 duration=format_duration(plan.estimated_duration_seconds)))

        self.settings.data["stone_farm"] = config
        self._save_settings_safely()
        args = (
            "start",
            "--pickaxe",
            config["pickaxe"],
            "--current-durability",
            config["current_durability"],
            "--minimum-durability",
            config["minimum_durability"],
            "--efficiency",
            config["efficiency"],
            "--unbreaking",
            config["unbreaking"],
            "--haste",
            config["haste"],
            "--calculation-method",
            config["calculation_method"],
            "--calibrated-seconds-per-durability",
            config["calibrated_seconds_per_durability"],
            "--auto-stop",
            int(bool(config["auto_stop"])),
        )
        self._run_script("stone-farm", *args)

    def _on_start_calibration(self, _button: Gtk.Button) -> None:
        self._stop_requested = False
        self._stone_completion_visible = False
        self._last_completion_was_calibration = False

        seconds = max(1.0, min(60.0, self.calibration_seconds_spin.get_value()))
        before = self.calibration_before_spin.get_value_as_int()
        if before < 1:
            self._append_log(_("Calibración inválida: la durabilidad inicial debe ser al menos 1."))
            return

        # Feedback inmediato mientras Bash prepara el proceso.
        self.stone_phase_label.set_text(_("PREPARACIÓN · CALIBRACIÓN"))
        self.stone_countdown_label.set_text("00:20")
        self.stone_countdown_caption.set_text(
            _("Prepárate: cambia a Minecraft y apunta al bloque de la cobblestone farm.")
        )
        self.stone_progress.set_fraction(0.0)
        self.stone_progress.set_text(_("Preparación 0%"))
        self.stone_live_timer_info.set_text(_("Preparación · 00:20"))

        config = self._stone_config()
        self.settings.data["stone_farm"] = config
        self._save_settings_safely()
        self._append_log(_(
            "Calibración iniciada | Duración de prueba: {seconds:.0f} s | "
            "Durabilidad inicial: {before} | Segundos/durabilidad actual: {rate:.3f} s"
        ).format(seconds=seconds, before=before,
                 rate=float(config["calibrated_seconds_per_durability"])))
        self._run_script(
            "stone-farm",
            "calibrate",
            "--seconds",
            f"{seconds:.0f}",
            "--initial-durability",
            before,
        )

    def _on_emergency_stop(self, _button: Gtk.Button) -> None:
        self._stop_requested = True
        self._stone_completion_visible = False
        self._run_script("minecraft-afk", "emergency-stop")

    def _run_script(self, name: str, *arguments: object) -> None:
        command = self.script_runner.build_command(name, *arguments)
        self._append_log(f"$ {command}")

        def worker() -> None:
            try:
                result = self.script_runner.execute(name, *arguments)
                GLib.idle_add(self._on_command_finished, result)
            except Exception as error:
                GLib.idle_add(self._on_command_error, command, str(error))

        threading.Thread(target=worker, daemon=True).start()

    def _on_command_finished(self, result: CommandResult) -> bool:
        if result.output:
            self._append_log(result.output)
        if result.returncode != 0:
            self._append_log(_("El comando terminó con código {code}.").format(code=result.returncode))
        self._refresh_runtime_status()
        return False

    def _on_command_error(self, command: str, message: str) -> bool:
        self._append_log(_("Error ejecutando {command}: {message}").format(command=command, message=message))
        self._refresh_runtime_status()
        return False

    # --------------------------------------------------------------- Runtime
    def _read_runtime_state(self) -> tuple[bool, str | None, dict[str, str]]:
        pid: str | None = None
        running = False
        try:
            pid = self.paths.pidfile.read_text(encoding="utf-8").splitlines()[0].strip()
            if pid.isdigit():
                os.kill(int(pid), 0)
                running = True
        except (FileNotFoundError, IndexError, OSError, ValueError):
            running = False

        state: dict[str, str] = {}
        if running:
            try:
                for line in self.paths.statefile.read_text(encoding="utf-8").splitlines():
                    if "=" in line:
                        key, value = line.split("=", 1)
                        state[key.strip()] = value.strip()
            except OSError:
                pass
        return running, pid if running else None, state

    @staticmethod
    def _state_float(value: str) -> float:
        """Convierte números del state file aceptando punto o coma decimal."""

        return float(value.strip().replace(",", "."))

    @staticmethod
    def _format_clock(seconds: float) -> str:
        """Formato de reloj para las cuentas regresivas de la Stone Farm."""

        total = max(0, int(seconds + 0.999))
        hours, remainder = divmod(total, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    def _stone_timer_snapshot(
        self, state: dict[str, str]
    ) -> tuple[str, str, str, float, str]:
        """Devuelve fase, reloj, explicación, progreso y texto de la barra."""

        if state.get("mode") != "stone_farm":
            return "ready", "--:--", _("Listo para iniciar"), 0.0, _("Esperando")

        try:
            started = self._state_float(state["start_epoch"])
            duration = max(
                0.0, self._state_float(state["estimated_duration_seconds"])
            )
            delay = max(
                0.0, self._state_float(state.get("start_delay_seconds", "20"))
            )
        except (KeyError, ValueError):
            return "ready", "--:--", _("Esperando datos del proceso"), 0.0, _("Esperando")

        now = time.time()

        run_type = state.get("run_type", "normal")

        if now < started:
            remaining = started - now
            if delay > 0:
                progress = max(0.0, min(1.0, 1.0 - remaining / delay))
            else:
                progress = 1.0
            percent = int(round(progress * 100))
            caption = (
                _("Cambia a Minecraft y apunta al bloque de la cobblestone farm. La prueba comenzará automáticamente.")
                if run_type == "calibration"
                else _("Cambia a Minecraft y apunta al bloque objetivo.")
            )
            return (
                "calibration_preparing" if run_type == "calibration" else "preparing",
                self._format_clock(remaining),
                caption,
                progress,
                _("Preparación {percent}%").format(percent=percent),
            )

        if state.get("auto_stop") != "1":
            return (
                "mining",
                "∞",
                _("Clic izquierdo mantenido · Auto-stop desactivado."),
                0.0,
                _("Minando sin límite"),
            )

        elapsed = max(0.0, now - started)
        remaining = max(0.0, duration - elapsed)
        progress = 1.0 if duration <= 0 else max(0.0, min(1.0, elapsed / duration))
        percent = int(round(progress * 100))
        if run_type == "calibration":
            return (
                "calibrating",
                self._format_clock(remaining),
                _("Prueba controlada: manteniendo el clic durante el tiempo seleccionado."),
                progress,
                _("Calibrando {percent}%").format(percent=percent),
            )

        return (
            "mining",
            self._format_clock(remaining),
            _("Tiempo restante hasta alcanzar la durabilidad mínima estimada."),
            progress,
            _("Minando {percent}%").format(percent=percent),
        )

    def _remaining_timer(self, state: dict[str, str]) -> str:
        phase, clock, _caption, _progress, _bar_text = self._stone_timer_snapshot(state)
        if phase in {"preparing", "calibration_preparing"}:
            return _("Preparación · {clock}").format(clock=clock)
        if phase == "calibrating":
            return _("Calibrando · {clock}").format(clock=clock)
        if phase == "mining":
            return _("Minando · {clock}").format(clock=clock)
        return "—"

    @staticmethod
    def _phase_label(phase: str) -> str:
        return {
            "ready": _("LISTO"),
            "preparing": _("PREPARACIÓN"),
            "calibration_preparing": _("PREPARACIÓN · CALIBRACIÓN"),
            "mining": _("MINANDO"),
            "calibrating": _("CALIBRANDO"),
        }[phase]

    def _refresh_runtime_status(self) -> bool:
        running, pid, state = self._read_runtime_state()
        mode = state.get("mode", "")
        mode_label = {
            "mob_farm": "Mob Farm",
            "stone_farm": _("Calibración Stone Farm")
            if state.get("run_type") == "calibration" else "Stone Farm",
        }.get(mode, "—")

        if running:
            self.global_status_label.set_text(_("{mode} activa").format(mode=mode_label))
            self.global_status_label.get_style_context().add_class("running")
        else:
            self.global_status_label.set_text(_("Detenido"))
            self.global_status_label.get_style_context().remove_class("running")

        self.mob_state_label.set_text(
            _("Activa") if running and mode == "mob_farm" else _("Detenida")
        )
        self.mob_start_button.set_sensitive(not running)
        calibration_mode = self.calibration_mode_switch.get_active()
        self.stone_start_button.set_sensitive(not running and not calibration_mode)
        self.calibration_start_button.set_sensitive(not running and calibration_mode)
        self.mob_stop_button.set_sensitive(running)
        self.stone_stop_button.set_sensitive(running)

        # Detecta un fin natural del auto-stop para dejar un estado visual de
        # "Completado" en vez de borrar inmediatamente el contador.
        previous = self._last_runtime_state
        if not running and previous.get("mode") == "stone_farm":
            try:
                expected_end = self._state_float(previous["start_epoch"]) + self._state_float(
                    previous["estimated_duration_seconds"]
                )
            except (KeyError, ValueError):
                expected_end = float("inf")
            if (
                previous.get("auto_stop") == "1"
                and not self._stop_requested
                and time.time() >= expected_end - 1.0
            ):
                self._stone_completion_visible = True
                self._last_completion_was_calibration = previous.get("run_type") == "calibration"

        remaining = self._remaining_timer(state) if running else "—"
        if running and mode == "stone_farm":
            phase, clock, caption, progress, bar_text = self._stone_timer_snapshot(state)
            self.stone_phase_label.set_text(self._phase_label(phase))
            self.stone_countdown_label.set_text(clock)
            self.stone_countdown_caption.set_text(caption)
            self.stone_progress.set_fraction(progress)
            self.stone_progress.set_text(bar_text)
            self.stone_live_timer_info.set_text(remaining)
            self._stone_completion_visible = False
        elif self._stone_completion_visible:
            if self._last_completion_was_calibration:
                self.stone_phase_label.set_text(_("CALIBRACIÓN COMPLETADA"))
                self.stone_countdown_label.set_text("00:00")
                self.stone_countdown_caption.set_text(
                    _("Prueba terminada. Mira la durabilidad del pico, escríbela en 'Prueba: durabilidad después' y pulsa CALCULAR Y GUARDAR CALIBRACIÓN.")
                )
                self.stone_progress.set_fraction(1.0)
                self.stone_progress.set_text(_("Calibración 100%"))
                self.stone_live_timer_info.set_text(_("Calibración completada"))
            else:
                self.stone_phase_label.set_text(_("OBJETIVO COMPLETADO"))
                self.stone_countdown_label.set_text("00:00")
                self.stone_countdown_caption.set_text(
                    _("Tiempo objetivo finalizado. El clic izquierdo fue liberado.")
                )
                self.stone_progress.set_fraction(1.0)
                self.stone_progress.set_text(_("Completado 100%"))
                self.stone_live_timer_info.set_text(_("Completado"))
        else:
            self.stone_phase_label.set_text(_("LISTO"))
            self.stone_countdown_label.set_text("--:--")
            self.stone_countdown_caption.set_text(_("Listo para iniciar"))
            self.stone_progress.set_fraction(0.0)
            self.stone_progress.set_text(_("Esperando"))
            self.stone_live_timer_info.set_text("—")

        durability = "—"
        enchantments = "—"
        expected_blocks = "—"
        if running and mode == "stone_farm":
            if state.get("run_type") == "calibration":
                durability = _("Inicio: {durability}").format(durability=state.get("current_durability", "—"))
                enchantments = _("Prueba de {seconds} s").format(seconds=state.get(
                    "calibration_duration_seconds", state.get("estimated_duration_seconds", "—")))
                expected_blocks = _("Midiendo")
            else:
                durability = (
                    f"{state.get('current_durability', '—')} → "
                    f"{state.get('minimum_durability', '—')}"
                )
                method_label = (
                    _("Calibrado") if state.get("calculation_method") == "calibrated" else _("Teórico")
                )
                enchantments = (
                    f"Efficiency {state.get('efficiency', '0')} · "
                    f"Unbreaking {state.get('unbreaking', '0')} · "
                    f"Haste {state.get('haste', '0')} · {method_label}"
                )
                expected_blocks = state.get("expected_blocks", "—")

        values = {
            "running": _("ACTIVO") if running else _("DETENIDO"),
            "mode": mode_label if running else "—",
            "pid": pid or "—",
            "interval": self._format_seconds(state.get("interval"))
            if running and mode == "mob_farm"
            else "—",
            "pickaxe": _(state.get("pickaxe", "—")) if running and mode == "stone_farm" else "—",
            "durability": durability,
            "enchantments": enchantments,
            "expected_blocks": expected_blocks,
            "timer": remaining,
        }
        for key, value in values.items():
            self._status_fields[key].set_text(value)
        if running:
            self._last_runtime_state = dict(state)
        elif self._stop_requested:
            self._last_runtime_state = {}
            self._stop_requested = False
        return True

    @staticmethod
    def _format_seconds(value: str | None) -> str:
        return f"{value} s" if value else "—"

    # ------------------------------------------------------------------ Logs
    def _append_log(self, message: str) -> None:
        message = message.rstrip()
        if not message:
            return
        end = self.log_buffer.get_end_iter()
        self.log_buffer.insert(end, message + "\n")
        mark = self.log_buffer.create_mark(None, self.log_buffer.get_end_iter(), False)
        self.log_view.scroll_to_mark(mark, 0.0, True, 0.0, 1.0)

    # ---------------------------------------------------------------- Styling
    def _install_css(self) -> None:
        css = b"""
        * {
            font-family: Sans;
        }
        window, .app-root {
            background: #0f1824;
            color: #f3f6fb;
        }
        .app-title {
            font-size: 20px;
            font-weight: 700;
        }
        .section-title {
            font-size: 18px;
            font-weight: 700;
        }
        .card-title, .summary-title {
            font-size: 16px;
            font-weight: 700;
            color: #f4f7fb;
        }
        .muted {
            color: #9aabc0;
        }
        .warning-text {
            color: #c7a96b;
        }
        .form-label {
            color: #e0e7f1;
            font-weight: 500;
        }
        .info-value {
            font-size: 15px;
            font-weight: 700;
            color: #f4f7fb;
        }
        .timer-phase {
            font-size: 13px;
            font-weight: 700;
            color: #d7e4f5;
            letter-spacing: 0.2px;
        }
        .countdown-value {
            font-size: 42px;
            font-weight: 700;
            font-family: monospace;
            color: #ffffff;
            padding: 2px 0;
        }
        .stone-progress {
            min-height: 10px;
            margin-top: 6px;
            margin-bottom: 8px;
        }
        progressbar trough {
            background: #1c2938;
            border: 0;
            border-radius: 6px;
            min-height: 8px;
        }
        progressbar progress {
            background: #198cff;
            border: 0;
            border-radius: 6px;
            min-height: 8px;
        }
        .card {
            background: #162231;
            border: 1px solid #2a394a;
            border-radius: 11px;
        }
        .info-callout {
            background: #1a2736;
            border: 1px solid #304155;
            border-radius: 9px;
        }
        separator {
            background: #2b3a4a;
            min-height: 1px;
        }
        .status-pill {
            padding: 7px 11px;
            border-radius: 14px;
            background: #1c2938;
            color: #b9c6d7;
        }
        .status-pill.running {
            color: #d9f6e5;
            background: #1f3c31;
        }
        button {
            min-height: 34px;
            border-radius: 7px;
            border: 1px solid #36485c;
            background: #1a2736;
            color: #e9eef6;
            padding: 6px 12px;
        }
        button:hover {
            background: #213145;
        }
        button:disabled {
            color: #718096;
            background: #17212d;
        }
        .primary-button {
            background: #2387f5;
            border-color: #2387f5;
            color: white;
            font-weight: 700;
            min-height: 40px;
        }
        .primary-button:hover {
            background: #3393ff;
        }
        .calibration-button {
            background: #7446d9;
            border-color: #7446d9;
            color: white;
            font-weight: 700;
            min-height: 40px;
        }
        .calibration-button:hover {
            background: #8153e4;
        }
        .secondary-button {
            background: #1a2736;
            border-color: #34485d;
            color: #c7d1df;
            font-weight: 600;
            min-height: 40px;
        }
        .danger-button {
            background: #b83d46;
            border-color: #b83d46;
            color: white;
            font-weight: 700;
        }
        notebook > header {
            background: #0d1621;
            border-bottom: 1px solid #243244;
        }
        notebook > header tab {
            padding: 10px 18px;
            color: #91a0b3;
            border: 0;
            background: transparent;
        }
        notebook > header tab:checked {
            color: #ffffff;
            background: #142131;
            border-bottom: 3px solid #2387f5;
        }
        entry, spinbutton, combobox, combobox button {
            min-height: 30px;
            border-radius: 6px;
            background: #1e2c3c;
            color: #e8eef6;
            border: 1px solid #34465a;
        }
        spinbutton entry {
            background: transparent;
            border: 0;
        }
        checkbutton {
            color: #e0e7f1;
        }
        switch.calibration-toggle {
            min-width: 44px;
            min-height: 24px;
            border-radius: 13px;
            border: 1px solid #3a4c60;
            background: #223143;
            padding: 2px;
            color: transparent;
        }
        switch.calibration-toggle:checked {
            background: #2387f5;
            border-color: #2387f5;
        }
        switch.calibration-toggle slider {
            min-width: 20px;
            min-height: 20px;
            border-radius: 10px;
            border: 0;
            background: #f4f7fb;
            box-shadow: none;
        }
        switch.calibration-toggle:disabled {
            background: #17212d;
            border-color: #2b3948;
        }
        .toggle-state {
            color: #8fa0b4;
            font-size: 12px;
            font-weight: 600;
        }
        .toggle-state.active {
            color: #75baff;
        }
        textview {
            background: #0b121b;
            color: #dbe4ef;
            font-family: monospace;
        }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        screen = Gdk.Screen.get_default()
        if screen is not None:
            Gtk.StyleContext.add_provider_for_screen(
                screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

    def _on_destroy(self, *_args: object) -> None:
        if self._status_timer_id is not None:
            GLib.source_remove(self._status_timer_id)
            self._status_timer_id = None
        self._save_settings_safely()
