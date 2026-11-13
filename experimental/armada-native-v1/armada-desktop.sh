#!/usr/bin/bash
# Fedora Plasma 6.7.5 compatibility packages retain X11 screen support.
# GPU rendering uses Zink with CPU presentation to the EFI framebuffer.
dbus-update-activation-environment --all
printf '%s' "$DBUS_SESSION_BUS_ADDRESS" >/run/armada-session-bus
chmod 600 /run/armada-session-bus
kwin_x11 --replace >/run/armada-kwin.log 2>&1 &
sleep 3
qdbus-qt6 org.kde.KWin /KWin supportInformation >/run/armada-kwin-support.log 2>&1
kbuildsycoca6 --noincremental >/run/armada-kde-cache.log 2>&1
kded6 >/run/armada-kded.log 2>&1 &
plasmashell --no-respawn >/run/armada-plasma.log 2>&1 &
ppid=$!
sleep 8
konsole --separate -e /usr/bin/bash /armada-info.sh >/run/armada-konsole.log 2>&1 &
wait "$ppid"
