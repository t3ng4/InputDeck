import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from inputdeck import lights

LIST = """0: Palit GeForce RTX 3080 LHR
1: ASRock Z690 Phantom Gaming 4
"""


class Fake:
    def __init__(self, code=0, out=""):
        self.code, self.out, self.calls = code, out, []

    def __call__(self, cmd, timeout=None):
        self.calls.append((cmd, timeout))
        return self.code, self.out


def rgb(code=0, out="", installed=True):
    fake = Fake(code, out)
    return lights.OpenRGB(runner=fake, which=lambda n: "/usr/bin/" + n if installed else None), fake


class ParsingTests(unittest.TestCase):
    def test_device_list(self):
        devices = lights.parse_device_list(LIST)
        self.assertEqual([(d.index, d.name) for d in devices],
                         [(0, "Palit GeForce RTX 3080 LHR"), (1, "ASRock Z690 Phantom Gaming 4")])

    def test_detail_lines_are_not_devices(self):
        text = "0: ASRock Z690 Phantom Gaming 4\n  Type: Motherboard\n  Modes: Static\n  LEDs: 3\n"
        self.assertEqual([d.name for d in lights.parse_device_list(text)], ["ASRock Z690 Phantom Gaming 4"])

    def test_colour_normalising(self):
        self.assertEqual(lights.normalize_color("#ff8800"), "FF8800")
        self.assertEqual(lights.normalize_color(" 00ff00 "), "00FF00")
        for bad in ("", "fff", "gg0000", "ff88001", "--color"):
            self.assertIsNone(lights.normalize_color(bad))


class SettingTests(unittest.TestCase):
    def test_validation(self):
        ok = lights.LightSetting("Board", "Static", "FF0000", 50)
        self.assertEqual(ok.problem(), "")
        self.assertTrue(lights.LightSetting("", "Static").problem())
        self.assertTrue(lights.LightSetting("-d", "Static").problem())
        self.assertTrue(lights.LightSetting("Board", "--help").problem())
        self.assertTrue(lights.LightSetting("Board", "Static", "red").problem())
        self.assertTrue(lights.LightSetting("Board", "Static", "FF0000", 101).problem())

    def test_roundtrip(self):
        s = lights.LightSetting("Board", "Breathing", "#00ff00", 40)
        again = lights.LightSetting.from_dict("Board", s.to_dict())
        self.assertEqual((again.mode, again.color, again.brightness), ("Breathing", "00FF00", 40))
        no_b = lights.LightSetting.from_dict("Board", lights.LightSetting("Board").to_dict())
        self.assertIsNone(no_b.brightness)

    def test_saved_settings_ignore_garbage(self):
        data = {"lights": {"Board": {"mode": "Static", "color": "112233"}, "Bad": "nope", 5: {}}}
        self.assertEqual([s.device for s in lights.saved_settings(data)], ["Board"])
        self.assertEqual(lights.saved_settings({"lights": ["x"]}), [])
        self.assertEqual(lights.saved_settings({}), [])
        self.assertIsNone(lights.LightSetting.from_dict("B", {"brightness": True}).brightness)


class ArgsTests(unittest.TestCase):
    def test_static_with_colour_and_brightness(self):
        args = lights.build_args([lights.LightSetting("ASRock Z690 Phantom Gaming 4", "Static", "ff8800", 60)])
        self.assertEqual(args, ["--device", "ASRock Z690 Phantom Gaming 4", "--mode", "Static",
                                "--color", "FF8800", "--brightness", "60"])

    def test_colourless_mode_and_default_brightness(self):
        args = lights.build_args([lights.LightSetting("Board", "Off", "FF0000")])
        self.assertEqual(args, ["--device", "Board", "--mode", "Off"])

    def test_several_devices_in_one_run(self):
        args = lights.build_args([lights.LightSetting("A", "Static", "FF0000"),
                                  lights.LightSetting("B", "Breathing", "0000FF")])
        self.assertEqual(args.count("--device"), 2)
        self.assertEqual(args.index("B"), args.index("--device", 2) + 1)


class OpenRGBTests(unittest.TestCase):
    def test_list_devices(self):
        client, fake = rgb(0, LIST)
        error, devices, raw = client.list_devices()
        self.assertEqual((error, len(devices), raw), ("", 2, LIST))
        self.assertEqual(fake.calls[0][0], ["openrgb", "--list-devices"])
        self.assertGreaterEqual(fake.calls[0][1], 30)

    def test_not_installed(self):
        client, fake = rgb(installed=False)
        self.assertIn("not installed", client.list_devices()[0])
        self.assertEqual(client.apply([lights.LightSetting("B")])[0], 1)
        self.assertEqual(fake.calls, [])

    def test_failure_and_empty(self):
        self.assertIn("denied", rgb(1, "permission denied")[0].list_devices()[0])
        self.assertIn("no devices", rgb(0, "")[0].list_devices()[0].lower())

    def test_apply_runs_one_command(self):
        client, fake = rgb(0, "")
        self.assertEqual(client.apply([lights.LightSetting("Board", "Static", "FF0000")])[0], 0)
        self.assertEqual(fake.calls[0][0][:3], ["openrgb", "--device", "Board"])

    def test_error_text_counts_as_failure_even_with_exit_code_zero(self):
        client, _ = rgb(0, "Error: Mode 'Static' not available for device 'Palit GeForce RTX 3080 LHR'")
        code, message = client.apply([lights.LightSetting("Palit GeForce RTX 3080 LHR", "Static", "FF0000")])
        self.assertEqual(code, 1)
        self.assertIn("not available", message)
        self.assertIn("Direct", message)

    def test_quiet_success_stays_success(self):
        self.assertEqual(rgb(0, "")[0].apply([lights.LightSetting("Board")]), (0, ""))
        self.assertEqual(rgb(0, "Applying settings")[0].apply([lights.LightSetting("Board")])[0], 0)

    def test_apply_refuses_invalid_settings(self):
        client, fake = rgb()
        code, message = client.apply([lights.LightSetting("Board", "Static", "nope")])
        self.assertEqual(code, 1)
        self.assertIn("colour", message)
        self.assertEqual(fake.calls, [])


class RatbagTests(unittest.TestCase):
    def status(self, code, out, installed=True):
        fake = Fake(code, out)
        return lights.ratbag_status(runner=fake, which=lambda n: "/x" if installed else None)

    def test_missing(self):
        self.assertEqual(self.status(0, "", installed=False)[0], "missing")

    def test_no_supported_mouse(self):
        state, text = self.status(0, "No devices available.\n")
        self.assertEqual(state, "none")
        self.assertIn("supported by libratbag", text)
        self.assertEqual(self.status(1, "No devices available.")[0], "none")

    def test_supported_and_error(self):
        self.assertEqual(self.status(0, "sinowealth0:  Some Mouse\n")[0], "found")
        self.assertEqual(self.status(1, "Unable to connect to ratbagd")[0], "error")
        self.assertEqual(self.status(0, "")[0], "error")


class I2CAccessTests(unittest.TestCase):
    def test_usable_bus(self):
        state, _ = lights.i2c_access(listing=lambda: ["/dev/i2c-0", "/dev/i2c-1"],
                                     can_use=lambda path: path == "/dev/i2c-1")
        self.assertEqual(state, "ok")

    def test_buses_exist_but_not_allowed(self):
        state, text = lights.i2c_access(listing=lambda: ["/dev/i2c-0"], can_use=lambda path: False)
        self.assertEqual(state, "denied")
        self.assertIn("usermod -aG i2c", text)

    def test_module_not_loaded(self):
        state, text = lights.i2c_access(listing=lambda: [], can_use=lambda path: True)
        self.assertEqual(state, "missing")
        self.assertIn("modprobe i2c-dev", text)


if __name__ == "__main__":
    unittest.main()
