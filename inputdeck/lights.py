from __future__ import annotations

import glob
import os
import re
import shutil
from dataclasses import dataclass
from typing import Callable, Optional

from . import core

OPENRGB_TIMEOUT = 60.0
DEFAULT_MODES = ("Static", "Off", "Breathing", "Spectrum Cycle", "Rainbow", "Wave", "Strobe", "Flashing", "Direct")
COLORLESS_MODES = {"off", "rainbow", "spectrum cycle", "cycle", "random", "rainbow wave"}
_HEX = re.compile(r"^#?([0-9a-fA-F]{6})$")
_DEVICE_LINE = re.compile(r"^(\d+):\s+(\S.*?)\s*$")


def normalize_color(text: str) -> Optional[str]:
    m = _HEX.match((text or "").strip())
    return m.group(1).upper() if m else None


def valid_mode(mode: str) -> bool:
    mode = (mode or "").strip()
    return 0 < len(mode) <= 40 and not mode.startswith("-") and mode.isprintable()


@dataclass
class LightSetting:
    device: str
    mode: str = "Static"
    color: str = "FFFFFF"
    brightness: Optional[int] = None

    def problem(self) -> str:
        if not self.device.strip() or self.device.startswith("-"):
            return "No device chosen."
        if not valid_mode(self.mode):
            return f"“{self.mode}” is not a usable mode name."
        if normalize_color(self.color) is None:
            return f"“{self.color}” is not a colour (use six hex digits, like FF8800)."
        if self.brightness is not None and not 0 <= self.brightness <= 100:
            return "Brightness must be between 0 and 100."
        return ""

    def to_dict(self) -> dict:
        data = {"mode": self.mode.strip(), "color": normalize_color(self.color) or "FFFFFF"}
        if self.brightness is not None:
            data["brightness"] = int(self.brightness)
        return data

    @classmethod
    def from_dict(cls, device: str, data: dict) -> "LightSetting":
        brightness = data.get("brightness")
        return cls(device, str(data.get("mode", "Static")), str(data.get("color", "FFFFFF")),
                   brightness if isinstance(brightness, int) and not isinstance(brightness, bool) else None)


def build_args(settings: list) -> list:
    args: list = []
    for s in settings:
        args += ["--device", s.device, "--mode", s.mode.strip()]
        if s.mode.strip().lower() not in COLORLESS_MODES:
            args += ["--color", normalize_color(s.color) or "FFFFFF"]
        if s.brightness is not None:
            args += ["--brightness", str(int(s.brightness))]
    return args


@dataclass
class LightDevice:
    index: int
    name: str


def parse_device_list(text: str) -> list:
    devices = []
    for line in text.splitlines():
        m = _DEVICE_LINE.match(line)
        if m:
            devices.append(LightDevice(int(m.group(1)), m.group(2)))
    return devices


def _reports_error(output: str) -> bool:
    return any(line.strip().lower().startswith("error") for line in output.splitlines())


def _with_hint(output: str) -> str:
    if "not available for device" in output:
        return (output.strip() + "\nThis device has no mode with that name. Try another mode in the box "
                "(graphics cards often only offer “Direct”); “Details…” shows what OpenRGB lists.")
    return output


class OpenRGB:
    def __init__(self, runner: Callable = core._run, which: Callable = shutil.which):
        self.runner, self.which = runner, which

    def available(self) -> bool:
        return bool(self.which("openrgb"))

    def list_devices(self) -> tuple:
        if not self.available():
            return "OpenRGB is not installed.", [], ""
        code, out = self.runner(["openrgb", "--list-devices"], OPENRGB_TIMEOUT)
        devices = parse_device_list(out)
        if code != 0 and not devices:
            return out or "OpenRGB failed.", [], out
        if not devices:
            return "OpenRGB found no devices it can control.", [], out
        return "", devices, out

    def apply(self, settings: list) -> tuple:
        if not self.available():
            return 1, "OpenRGB is not installed."
        for s in settings:
            if s.problem():
                return 1, s.problem()
        if not settings:
            return 0, ""
        code, out = self.runner(["openrgb", *build_args(settings)], OPENRGB_TIMEOUT)
        if code == 0 and _reports_error(out):
            code = 1
        return code, _with_hint(out) if code else out


def saved_settings(settings: dict) -> list:
    saved = settings.get("lights")
    if not isinstance(saved, dict):
        return []
    return [LightSetting.from_dict(name, data) for name, data in saved.items()
            if isinstance(name, str) and isinstance(data, dict)]


I2C_HELP = (
    "Graphics cards and some RAM or motherboard lighting are controlled over the I2C bus. "
    "OpenRGB stays silent when it is not allowed to use it, so the lights simply don't change.\n"
    "Fix: load the module with `sudo modprobe i2c-dev` (make it permanent with a file in /etc/modules-load.d/ "
    "containing `i2c-dev`), then add yourself to the i2c group: `sudo usermod -aG i2c $USER`, "
    "and log out and in again."
)


def i2c_access(listing: Callable = lambda: sorted(glob.glob("/dev/i2c-*")),
               can_use: Callable = lambda path: os.access(path, os.R_OK | os.W_OK)) -> tuple:
    buses = listing()
    if not buses:
        return "missing", "No /dev/i2c-* devices: the i2c-dev kernel module is not loaded.\n" + I2C_HELP
    if any(can_use(b) for b in buses):
        return "ok", "I2C buses are accessible."
    return "denied", "You are not allowed to use the I2C buses (" + ", ".join(buses) + ").\n" + I2C_HELP


def ratbag_status(runner: Callable = core._run, which: Callable = shutil.which) -> tuple:
    if not which("ratbagctl"):
        return "missing", "libratbag (ratbagctl) is not installed."
    code, out = runner(["ratbagctl", "list"], 15.0)
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    if any("no devices" in ln.lower() for ln in lines):
        return "none", ("None of your mice is supported by libratbag, so DPI and polling rate can't be "
                        "changed from Linux with it.")
    if code != 0 or not lines:
        return "error", out or "ratbagctl could not talk to ratbagd (is the ratbagd service running?)."
    return "found", "\n".join(lines)


def piper_command(which: Callable = shutil.which) -> Optional[list]:
    return ["piper"] if which("piper") else None
