# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and versions follow [Semantic Versioning](https://semver.org/).

## [0.5.1] - 2026-11-15

### Fixed
- The built-in engine could refuse a connection right after starting: its socket file appeared before it
  was listening, so a client connecting in that moment thought no engine was running. The socket now only
  appears once it accepts connections.
- CI: the test workflow runs on Ubuntu 24.04 instead of `ubuntu-latest`, which moved to 26.04 and has no
  Python 3.9 build. All five Python versions (3.9 to 3.13) are tested again.

## [0.5.0] - 2026-11-14

### Added
- **Hardware tab.** Lighting through OpenRGB: detect devices, choose mode, colour and brightness, apply,
  save per device, and optionally restore at startup. OpenRGB is only run when you press a button (or when
  startup restore is on), never in the background.
- DPI and polling rate for mice that libratbag supports: the tab checks support and opens Piper. If libratbag
  doesn't know the mouse, it says so instead of guessing.
- An I2C access check on the Hardware tab. Graphics-card lighting needs the `i2c-dev` module and access to
  `/dev/i2c-*`; without them OpenRGB fails silently. *Details…* now explains what is missing and how to fix it.
- An OpenRGB run that prints `Error: …` but exits with code 0 (for example "Mode 'Static' not available")
  is shown as a failure, with a hint to try another mode such as `Direct`.

### Notes
- InputDeck does not write to mouse firmware itself. Lighting was tested on one machine, through the tab:
  an ASRock motherboard and a Palit RTX 3080 LHR graphics card. Other devices and modes depend on what
  OpenRGB supports. The libratbag part detects support and starts Piper;
  it does not read or change DPI itself.

## [0.4.0] - 2026-11-01

### Added
- **Window-aware auto-switch rules.** Each rule now has a *While* setting: *running* (as before), *window
  visible* (on screen, not minimized, not hidden in the tray, on the current desktop) or *window focused*.
  Use it to give a game its preset only while you can see it and fall back to your desktop preset while
  it is minimized or sitting in the tray.
- A switch on the Auto-switch tab to turn window checks off, plus a status line showing whether window
  detection works. Setup check / `--check` report it as an optional item.
- `rules.txt` takes an optional fourth field (`process|device|preset|visible`); existing files and Saito's
  `config.txt` format work unchanged.
- `install.sh` offers to install `xprop` (`xorg-xprop`, `x11-utils` or `xorg-x11-utils`).

### Notes
- Window detection uses `xprop`: all windows on X11, and windows of X11 programs (including Wine/Proton
  games) on Wayland. Native Wayland windows can't be seen by other programs; without detection, window
  rules act like "running" and the log says so.

## [0.3.0] - 2026-10-31

### Added
- The preset that is actually running is now shown everywhere: a banner above the mappings, a green
  marker on the preset list and in the device list, and a summary on the Auto-switch tab. InputDeck opens
  on the running preset instead of "Default".
- **Logs** menu: live viewers for the engine log and the auto-switch/app log, copy-all, open log folder.
- **Help** menu: link to the GitHub page and to the issue tracker.
- A warning (dialog on manual Apply, note in the auto-switch log) when mappings had to be skipped, e.g. a
  broken macro, instead of failing silently.
- **Reset to defaults** (menu, or `inputdeck --reset`): stops all remapping and the built-in engine, resets
  InputDeck's settings; presets, rules and the macro library are never touched.
- The engine logs which process sent each request, and log files are rotated.

### Changed
- The **File** menu is now **Options**.
- Own application icon.

### Fixed
- The built-in engine could not start on real systems (python-evdev devices cannot be used as dictionary
  keys). Any failure while starting now releases the device again.
- Virtual output devices are created up front, so the first key of a macro is no longer lost.
- Kernel autorepeat events are no longer forwarded twice.
- The engine no longer exits and restarts in a loop while a client keeps talking to it.

## [0.2.0] and earlier - development builds

- Device detection grouped like input-remapper, key/hotkey recording, macro recording with timing,
  loop modes (repeat while held / toggle), auto-switching per program, macro library with right-click
  assignment, About dialog, Saito `config.txt` import, stale device-ID repair.
- Experimental built-in remapping engine (no input-remapper needed).
- Installer for Arch-, Debian- and Fedora-based systems.
