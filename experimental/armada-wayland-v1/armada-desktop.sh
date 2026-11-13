#!/usr/bin/bash
export QT_QPA_PLATFORM=wayland
unset QT_IM_MODULE QT_SCALE_FACTOR QT_FONT_DPI
dbus-update-activation-environment --all
printf '%s' "$DBUS_SESSION_BUS_ADDRESS" >/run/armada-session-bus
chmod 600 /run/armada-session-bus
kscreen-doctor -o >/run/armada-outputs.log 2>&1
kscreen-doctor output.1.scale.1.25 >>/run/armada-outputs.log 2>&1
qdbus-qt6 org.kde.KWin /KWin supportInformation >/run/armada-kwin-support.log 2>&1
kbuildsycoca6 --noincremental >/run/armada-kde-cache.log 2>&1
kded6 >/run/armada-kded.log 2>&1 &
plasmashell --no-respawn >/run/armada-plasma.log 2>&1 &
ppid=$!
sleep 8
konsole --separate >/run/armada-konsole.log 2>&1 &
wait "$ppid"
