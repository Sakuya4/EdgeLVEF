# EdgeLVEF FRDM i.MX93 — 480x320 Instrument UI

This GTK3 application is a fullscreen prototype for a 3.5-inch 480x320 RPi LCD
on FRDM i.MX93. It automatically loops `test_data/plax.avi` as a stand-in for a
future probe and preserves the existing frame-buffer and EdgeLVEF pipeline.

## Instrument screen

The application has no title bar, menus, file selector, status/debug panel,
Save button, or mouse controls. The upper expanding area shows the ultrasound
image with aspect ratio preserved and black letterboxing. The bottom fixed
82-pixel strip contains three equal cells:

```text
┌──────────────────────────────────────────────┐
│             ultrasound image                │
│                                              │
├───────────────┬──────────────┬───────────────┤
│   MAX LVEF    │   AVG LVEF   │   MIN LVEF    │
│      --       │      --      │      --       │
└───────────────┴──────────────┴───────────────┘
```

The window requests 480x320, removes decorations, enters GTK fullscreen at
startup, and hides the cursor only over its own GDK window. Closing the process
restores normal cursor handling. Press **Escape** during development to exit.

## Measurement sessions and reset

`core/measurement_session.py` maintains the maximum, minimum, arithmetic mean,
and count for all valid LVEF estimations since the last reset. Only finite real
numbers from 0 through 100 are accepted. `None`, NaN, infinity, booleans,
strings, errors, and out-of-range values are ignored. Invalid inference results
therefore leave the display unchanged.

Press **R** to reset the measurement session without stopping video or AI. The
three values immediately return to `--`; the next valid result begins a new
session.

The optional GPIO input is configured in `config.py` or with environment
variables:

```sh
export EDGELVEF_RESET_GPIO_CHIP=/dev/gpiochip0
export EDGELVEF_RESET_GPIO_LINE=7
```

These values are placeholders—verify the actual chip/line and active electrical
level on the final board before setting them. The current adapter expects a
falling edge and uses the libgpiod v1 Python API. If configuration, permission,
the `gpiod` module, or line acquisition fails, the app prints a warning and
continues with keyboard R available. GPIO callbacks return to the GTK thread via
`GLib.idle_add`.

## Manual launch on FRDM i.MX93

Deploy this directory at `/opt/edgelvef_app`, place the MJPEG test cine at
`/opt/edgelvef_app/test_data/plax.avi`, then run:

```sh
chmod +x /opt/edgelvef_app/run.sh
/opt/edgelvef_app/run.sh
```

`run.sh` changes to its own directory, supplies the current X11 compatibility
environment, waits up to 60 seconds for the XWayland `:0` socket, and executes
`python3 -u main.py`. The bounded wait prevents rapid failures during boot. The
existing AVI EOF behavior remains release → reopen `VideoCapture` → continue.

## systemd autostart and crash restart

`deployment/edgelvef.service` assumes the project is `/opt/edgelvef_app`, runs
as root, uses XWayland `DISPLAY=:0`, `/run/user/0`, and a `weston.service` unit.

```sh
install -m 644 /opt/edgelvef_app/deployment/edgelvef.service \
  /etc/systemd/system/edgelvef.service
systemctl daemon-reload
systemctl enable --now edgelvef.service
systemctl status edgelvef.service
journalctl -u edgelvef.service -f
```

It starts after Weston/graphical target, restarts on failure after two seconds,
and applies a start-rate limit. Logs stay in the systemd journal.

**Board confirmation is required:** check the real Weston unit with
`systemctl list-units --type=service | grep -i weston`. If named differently,
edit `After=`. Confirm root can connect to XWayland; otherwise use the actual
graphical user and runtime directory. Also confirm fullscreen covers any Weston
panel under the image's compositor policy. Disable during debugging with
`systemctl disable --now edgelvef.service`.

## Scope and verification

- Target: 480x320 landscape; GTK3 over the existing X11 compatibility path.
- CPU provider remains unchanged; no NPU claim is made.
- No model, ONNX, smoothing, inference formula, FPS/pacing, video acquisition,
  AVI reopen loop, or probe/Wi-Fi implementation was changed for this UI.
- A short looping test AVI is not a medically valid continuous cardiac cine.
- This remains an unvalidated prototype.

```sh
python3 -m compileall -q .
python3 -m unittest discover -s tests -v
```

Tests cover statistics, invalid inputs, reset fallback, GPIO failure, 480x320
layout constants, service policy, existing AVI loop/pacing/buffer/session logic,
and shutdown. Fullscreen, cursor restoration, real GPIO mapping and libgpiod API,
XWayland access, Weston ordering, and boot autostart require FRDM i.MX93 testing.
