import gettext
import json
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from minecraft_afk.i18n import _, DOMAIN, LOCALE_DIR, resolve_language, set_language
from minecraft_afk.mining import PICKAXE_BY_KEY, calculate_calibration, calculate_stone_plan
from minecraft_afk.scripts import BashScriptRunner
from minecraft_afk.settings import SettingsStore


class LanguageTests(unittest.TestCase):
    def tearDown(self):
        set_language("es")

    def test_explicit_language_overrides_system(self):
        with patch.dict(os.environ, {"LANGUAGE": "en"}, clear=True):
            self.assertEqual(resolve_language("es"), "es")

    def test_system_language_variants_and_fallback(self):
        for environment, expected in (
            ({"LANG": "es_CL.UTF-8"}, "es"),
            ({"LANG": "en-US.UTF-8"}, "en"),
            ({"LANGUAGE": "pt_BR:en_GB:es", "LANG": "es_ES.UTF-8"}, "en"),
            ({"LC_ALL": "es_CL.UTF-8", "LANG": "en_US.UTF-8"}, "es"),
            ({"LC_MESSAGES": "en_GB.UTF-8", "LANG": "es_CL.UTF-8"}, "en"),
            ({"LANG": "de_DE.UTF-8"}, "es"),
            ({"LANG": "C"}, "es"),
        ):
            with self.subTest(environment=environment), patch.dict(os.environ, environment, clear=True):
                self.assertEqual(resolve_language("auto"), expected)
                self.assertEqual(resolve_language("invalid"), expected)

    def test_catalogs_and_labels_are_loaded_at_display_time(self):
        label = PICKAXE_BY_KEY["diamond"].label
        set_language("en")
        self.assertEqual(_("Ajustes"), "Settings")
        self.assertEqual(_(label), "Diamond pickaxe")
        self.assertEqual(_("Unknown untranslated message"), "Unknown untranslated message")
        set_language("es")
        self.assertEqual(_("Ajustes"), "Ajustes")
        self.assertEqual(_(label), "Pico de diamante")

    def test_validation_errors_and_calculations_in_both_languages(self):
        plans = []
        for language, message in (("en", "Initial durability"), ("es", "La durabilidad inicial")):
            set_language(language)
            with self.assertRaisesRegex(ValueError, message):
                calculate_calibration(10, 20, 30)
            plans.append(calculate_stone_plan("diamond", 962, 900, calculation_method="calibrated"))
        self.assertEqual(plans[0], plans[1])

    def test_settings_upgrade_and_language_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({"mob_farm": {"interval": 3.5}}))
            store = SettingsStore(path)
            self.assertEqual(store.data["language"], "auto")
            store.data["language"] = "en"
            store.save()
            reloaded = SettingsStore(path)
            self.assertEqual(reloaded.data["language"], "en")
            self.assertEqual(reloaded.data["mob_farm"]["interval"], 3.5)

    def test_shell_templates_preserve_format_arguments(self):
        # Shell uses printf-style placeholders; xgettext's Shell extractor
        # does not validate Python's percent formatting, so check it here.
        catalog = gettext.translation(DOMAIN, LOCALE_DIR, languages=["en"])
        for path in Path("scripts").glob("*.sh"):
            for template in re.findall(r"\bmessage '([^']*)'", path.read_text()):
                if "%s" in template:
                    with self.subTest(template=template):
                        translated = catalog.gettext(template)
                        self.assertNotEqual(translated, template)
                        values = tuple(f"ARG{i}" for i in range(template.count("%s")))
                        output = translated % values
                        for value in values:
                            self.assertIn(value, output)


class ScriptLanguageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.environment = patch.dict(os.environ, {
            "MINECRAFT_AFK_PIDFILE": str(Path(self.directory.name) / "afk.pid"),
            "MINECRAFT_AFK_STATEFILE": str(Path(self.directory.name) / "afk.state"),
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.runner = BashScriptRunner()

    def test_help_and_validation_output(self):
        for language, heading, error in (("es", "Uso:", "necesita un valor"), ("en", "Usage:", "requires a value")):
            self.runner.language = language
            for script in self.runner.available_scripts():
                with self.subTest(language=language, script=script):
                    result = self.runner.execute(script, "help")
                    self.assertEqual(result.returncode, 0)
                    self.assertTrue(result.stdout.startswith(heading))
            result = self.runner.execute("mob-farm", "start", "--interval")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(error, result.stderr)

    def test_machine_output_is_identical_across_languages(self):
        outputs = []
        for language in ("es", "en"):
            self.runner.language = language
            result = self.runner.execute("stone-farm", "calculate", "--current-durability", 962,
                                         "--minimum-durability", 900)
            self.assertEqual(result.returncode, 0, result.stderr)
            outputs.append(result.stdout)
        self.assertEqual(outputs[0], outputs[1])
        self.assertIn("pickaxe_key=diamond\n", outputs[0])
        self.assertIn("estimated_duration_seconds=91.39\n", outputs[0])

    def test_message_values_are_not_evaluated_as_shell(self):
        self.runner.language = "en"
        value = "$(printf BAD); %s"
        result = self.runner.execute("minecraft-afk", value)
        self.assertIn(f"Unknown command: {value}", result.stderr)
        self.assertEqual(result.returncode, 1)


if __name__ == "__main__":
    unittest.main()
