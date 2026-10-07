#!/usr/bin/env python3
"""One-shot native app window diagnostic; not a runtime frame relay.

Rootless XWayland's root and fbdev compatibility buffers are not app scanout.
Capture the actual GTK client window without modifying the compositor.
"""
import re
import subprocess
import gi
gi.require_version('Gdk', '3.0')
gi.require_version('GdkX11', '3.0')
from gi.repository import Gdk, GdkX11

tree = subprocess.check_output(['xwininfo', '-root', '-tree'], text=True)
match = re.search(r'(0x[0-9a-f]+) "EdgeLVEF"', tree)
if not match:
    raise SystemExit('Native EdgeLVEF window unavailable')
window = GdkX11.X11Window.foreign_new_for_display(Gdk.Display.get_default(), int(match[1], 16))
image = Gdk.pixbuf_get_from_window(window, 0, 0, window.get_width(), window.get_height())
if image is None:
    raise SystemExit('Native window capture failed')
image.savev('/opt/aco-sidecar/linux-live-ui.png', 'png', [], [])
print('NATIVE_APP_CAPTURED', image.get_width(), image.get_height())
