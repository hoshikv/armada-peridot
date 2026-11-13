#!/usr/bin/bash
# Desktop/menu launcher executed by the root-owned Plasma RAM session.
exec >>/run/steam-manual.log 2>&1
if pgrep -u armada -x steam >/dev/null; then
 echo 'Steam is already running.'; exit 0
fi
xhost +SI:localuser:armada
exec runuser -u armada -- env DISPLAY="$DISPLAY" /usr/bin/bash /steam-session.sh "$@"
