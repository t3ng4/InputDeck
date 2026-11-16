import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import qt_stub

qt_stub.install()
import test_recorder as tr
from inputdeck import core, gui, lights
from test_lights import LIST, Fake

wait_for = tr.wait_for
QMessageBox = qt_stub.QMessageBox


class HardwareTabTests(unittest.TestCase):
    def setUp(self):
        tr.reset()
        self.tmp = Path(tempfile.mkdtemp())
        self.paths = core.Paths(self.tmp / "ir", self.tmp / "cfg", self.tmp / "data")
        self.control = core.RemapperControl(runner=lambda c: (0, ""), binary="irc")
        self.state = gui.State(self.paths, self.paths.rules_file, self.control)
        self.fake = Fake(0, LIST)
        self.rgb = lights.OpenRGB(runner=self.fake, which=lambda n: "/usr/bin/" + n)
        self.ratbag_answer = ("none", "None of your mice is supported by libratbag")
        self.tab = gui.HardwareTab(self.state, None, rgb=self.rgb, ratbag=lambda: self.ratbag_answer)
        QMessageBox.log.clear()

    def tearDown(self):
        self.state.switcher.stop()

    def detect(self):
        self.tab.detect_btn.clicked.emit()
        self.assertTrue(wait_for(lambda: self.tab.device.count() == 2))
        self.assertTrue(wait_for(lambda: "device(s) found" in self.tab.status.text()))

    def test_nothing_runs_until_asked(self):
        self.assertEqual(self.fake.calls, [])

    def test_detect_fills_the_device_list(self):
        self.detect()
        self.assertEqual(self.tab.device.items, ["Palit GeForce RTX 3080 LHR", "ASRock Z690 Phantom Gaming 4"])
        self.assertIn("2 device", self.tab.status.text())
        self.assertTrue(self.tab.apply_btn.__dict__.get("_enabled", True))

    def test_apply_runs_openrgb_for_the_chosen_device(self):
        self.detect()
        self.tab.device.setCurrentText("ASRock Z690 Phantom Gaming 4")
        self.tab.mode.setCurrentText("Static")
        self.tab.color.setText("#ff8800")
        self.tab.bright_box.setChecked(True)
        self.tab.bright.setValue(70)
        self.fake.calls.clear()
        self.tab.apply_btn.clicked.emit()
        self.assertTrue(wait_for(lambda: self.fake.calls and self.tab.status.text().startswith("Applied")))
        self.assertEqual(self.fake.calls[0][0],
                         ["openrgb", "--device", "ASRock Z690 Phantom Gaming 4", "--mode", "Static",
                          "--color", "FF8800", "--brightness", "70"])
        log_file = self.paths.data_dir / "inputdeck.log"
        self.assertTrue(wait_for(lambda: log_file.exists() and "[lights] applied" in log_file.read_text()))

    def test_openrgb_error_is_shown(self):
        self.detect()
        self.fake.code, self.fake.out = 1, "Mode 'Foo' not available"
        self.tab.mode.setCurrentText("Static")
        self.tab.mode.items.append("Foo")
        self.tab.mode.setCurrentText("Foo")
        self.tab.apply_btn.clicked.emit()
        self.assertTrue(wait_for(lambda: "problem" in self.tab.status.text()))
        self.assertIn("not available", self.tab.status.text())

    def test_invalid_colour_does_not_run_anything(self):
        self.detect()
        self.fake.calls.clear()
        self.tab.color.setText("zzz")
        self.tab.apply_btn.clicked.emit()
        self.assertIn("colour", self.tab.status.text())
        self.assertEqual(self.fake.calls, [])

    def test_save_and_restore_per_device(self):
        self.detect()
        self.tab.device.setCurrentText("ASRock Z690 Phantom Gaming 4")
        self.tab.mode.setCurrentText("Breathing")
        self.tab.color.setText("00FF00")
        self.tab.save_btn.clicked.emit()
        saved = json_load(self.paths.settings_file)["lights"]
        self.assertEqual(saved["ASRock Z690 Phantom Gaming 4"]["mode"], "Breathing")
        self.tab.mode.setCurrentText("Static")
        self.tab.color.setText("FFFFFF")
        self.tab.device.setCurrentText("Palit GeForce RTX 3080 LHR")
        self.tab.device.setCurrentText("ASRock Z690 Phantom Gaming 4")
        self.assertEqual((self.tab.mode.currentText(), self.tab.color.text()), ("Breathing", "00FF00"))

    def test_apply_saved_only_when_enabled(self):
        self.state.settings["lights"] = {"Board": {"mode": "Static", "color": "112233"}}
        self.tab.apply_saved()
        self.assertEqual(self.fake.calls, [])
        self.tab.on_start.setChecked(True)
        self.assertTrue(json_load(self.paths.settings_file)["lights_on_start"])
        self.tab.apply_saved()
        self.assertTrue(wait_for(lambda: len(self.fake.calls) == 1))
        self.assertEqual(self.fake.calls[0][0][:6], ["openrgb", "--device", "Board", "--mode", "Static", "--color"])

    def test_colour_picker(self):
        qt_stub.QColorDialog.answer = "#12ab34"
        self.tab.pick_btn.clicked.emit()
        self.assertEqual(self.tab.color.text(), "12AB34")
        qt_stub.QColorDialog.answer = ""
        self.tab.pick_color()
        self.assertEqual(self.tab.color.text(), "12AB34")

    def test_mouse_without_libratbag_support(self):
        self.tab.mouse_btn.clicked.emit()
        self.assertTrue(wait_for(lambda: "libratbag" in self.tab.mouse_status.text()))

    def test_mouse_with_support(self):
        self.ratbag_answer = ("found", "sinowealth0: Some Mouse")
        self.tab.mouse_btn.clicked.emit()
        self.assertTrue(wait_for(lambda: "Open Piper" in self.tab.mouse_status.text()))

    def test_openrgb_missing_is_explained(self):
        rgb = lights.OpenRGB(runner=self.fake, which=lambda n: None)
        tab = gui.HardwareTab(self.state, None, rgb=rgb, ratbag=lambda: ("missing", "x"))
        self.assertIn("not installed", tab.status.text())
        tab.apply_saved()
        self.assertEqual(self.fake.calls, [])


def json_load(path):
    import json
    return json.loads(Path(path).read_text())


if __name__ == "__main__":
    unittest.main()
