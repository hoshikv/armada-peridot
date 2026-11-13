#!/usr/bin/bash
# Fedora Plasma 6.7.5 compatibility packages retain X11 screen support.
# KWin X11 runs without compositing on the validated framebuffer X server.
dbus-update-activation-environment DISPLAY XDG_RUNTIME_DIR LIBGL_ALWAYS_SOFTWARE QT_QUICK_BACKEND XDG_CURRENT_DESKTOP XDG_SESSION_TYPE QT_QPA_PLATFORM
kwin_x11 --replace >/run/armada-kwin.log 2>&1 &
sleep 3
kbuildsycoca6 --noincremental >/run/armada-kde-cache.log 2>&1
kded6 >/run/armada-kded.log 2>&1 &
plasmashell --no-respawn >/run/armada-plasma.log 2>&1 &
ppid=$!
sleep 8
konsole --separate -e /usr/bin/bash /armada-info.sh >/run/armada-konsole.log 2>&1 &
wait "$ppid"
