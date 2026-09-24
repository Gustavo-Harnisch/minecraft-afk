"""Optional real GTK tests; use a desktop session or xvfb-run.

MINECRAFT_AFK_GUI_TESTS=1 python3 -m unittest discover -s tests -p test_gui_i18n.py
"""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


@unittest.skipUnless(os.environ.get("MINECRAFT_AFK_GUI_TESTS") == "1", "GTK display test is opt-in")
class GtkLanguageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from minecraft_afk.window import MinecraftAfkWindow
        from minecraft_afk.config import ProjectPaths
        cls.Window = MinecraftAfkWindow
        cls.Paths = ProjectPaths

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.environment = patch.dict(os.environ, {"XDG_CONFIG_HOME": self.directory.name})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.config = Path(self.directory.name) / "minecraft-afk" / "config.json"
        self.config.parent.mkdir()
        root = Path(__file__).resolve().parent.parent
        self.paths = self.Paths(root, root / "scripts", Path(self.directory.name) / "afk.pid",
                                Path(self.directory.name) / "afk.state")

    def window(self, language):
        self.config.write_text(json.dumps({"language": language}))
        window = self.Window(paths=self.paths)
        self.addCleanup(window.destroy)
        # Never start real automation during GUI tests.
        window._run_script = lambda *args: None
        return window

    def test_visible_labels_and_timer_states(self):
        for language, tab, pickaxe, preparing, mining in (
            ("es", "Ajustes", "Pico de diamante", "Preparación", "Minando"),
            ("en", "Settings", "Diamond pickaxe", "Preparing", "Mining"),
        ):
            with self.subTest(language=language):
                window = self.window(language)
                page = window.notebook.get_nth_page(4)
                self.assertEqual(window.notebook.get_tab_label_text(page), tab)
                self.assertEqual(window.pickaxe_combo.get_active_text(), pickaxe)
                window._on_start_stone(None)
                self.assertEqual(window.stone_phase_label.get_text(), preparing.upper())
                state = {"mode": "stone_farm", "start_epoch": "1020", "start_delay_seconds": "20",
                         "estimated_duration_seconds": "60", "auto_stop": "1"}
                with patch("minecraft_afk.window.time.time", return_value=1005):
                    self.assertEqual(window._stone_timer_snapshot(state)[0], "preparing")
                    self.assertEqual(window._remaining_timer(state), f"{preparing} · 00:15")
                with patch("minecraft_afk.window.time.time", return_value=1030):
                    self.assertEqual(window._stone_timer_snapshot(state)[0], "mining")
                    self.assertEqual(window._remaining_timer(state), f"{mining} · 00:50")
                    state["run_type"] = "calibration"
                    self.assertEqual(window._stone_timer_snapshot(state)[0], "calibrating")
                    state["auto_stop"] = "0"
                    self.assertEqual(window._stone_timer_snapshot(state)[1], "∞")
                window.destroy()

    def test_language_change_is_saved_and_applied_on_restart(self):
        window = self.window("es")
        window.mob_interval.set_value(3.5)
        window.language_combo.set_active_id("en")
        saved = json.loads(self.config.read_text())
        self.assertEqual(saved["language"], "en")
        self.assertEqual(window.script_runner.language, "es")
        self.assertIn("Reinicia", window.language_notice.get_text())
        window.destroy()
        restarted = self.Window(paths=self.paths)
        self.addCleanup(restarted.destroy)
        self.assertEqual(restarted.script_runner.language, "en")
        self.assertEqual(restarted.mob_interval.get_value(), 3.5)
        self.assertEqual(restarted.mob_start_button.get_label(), "START MOB FARM")

    def test_save_failure_restores_language_selection(self):
        window = self.window("en")
        with patch.object(window.settings, "save", side_effect=OSError("read only")):
            window.language_combo.set_active_id("es")
        self.assertEqual(window.language_combo.get_active_id(), "en")
        self.assertEqual(window.settings.data["language"], "en")
        self.assertIn("Could not save", window.language_notice.get_text())


if __name__ == "__main__":
    unittest.main()
