#!/usr/bin/bash
export XDG_CURRENT_DESKTOP=KDE XDG_SESSION_DESKTOP=KDE
xsetroot -solid '#182b3a'
openbox >/run/openbox.log 2>&1 &
for path in dev proc sys run tmp; do
 mkdir -p "/armada/$path"
 mount --rbind "/$path" "/armada/$path" || exit 1
 mount --make-rslave "/armada/$path"
done
chroot /armada /usr/bin/bash /armada-session.sh >/run/armada-session.log 2>&1 &
apid=$!
for ((i=0;i<150;i++)); do
 while IFS= read -r window; do
  xdotool windowsize "$window" 1440 3168 windowmove "$window" 0 0 windowactivate "$window" 2>/dev/null
 done < <(xdotool search --onlyvisible --class 'kwin_wayland' 2>/dev/null)
 kill -0 "$apid" 2>/dev/null || break
 sleep 1
done
if kill -0 "$apid" 2>/dev/null; then wait "$apid"; fi
xterm -fa monospace -fs 18 -geometry 80x55+0+0 -title 'Armada RAM boot diagnostics' -e /usr/bin/bash -c 'cat /run/armada-session.log /run/armada-kwin.log /run/armada-plasma.log /run/armada-konsole.log; exec bash -i'
