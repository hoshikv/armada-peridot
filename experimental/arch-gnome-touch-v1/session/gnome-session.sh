#!/usr/bin/bash
# A development shell session, without systemd or physical-disk mounting.
export XDG_SESSION_TYPE=wayland GDK_BACKEND=x11
export GSETTINGS_BACKEND=keyfile
export GNOME_SHELL_SESSION_MODE=user
dbus-update-activation-environment DISPLAY XDG_RUNTIME_DIR LIBGL_ALWAYS_SOFTWARE GALLIUM_DRIVER GSK_RENDERER
export GI_TYPELIB_PATH=/usr/lib/girepository-1.0
while IFS= read -r path; do
 export GI_TYPELIB_PATH="${path%/*}:$GI_TYPELIB_PATH"
done < <(find /usr/lib -name 'Meta-*.typelib')
gsettings set org.gnome.desktop.interface enable-animations false
gsettings set org.gnome.desktop.session idle-delay 0
gsettings set org.gnome.desktop.screensaver lock-enabled false
gsettings set org.gnome.desktop.media-handling automount false
gsettings set org.gnome.desktop.media-handling automount-open false
gsettings set org.gnome.desktop.media-handling autorun-never true
gsettings set org.gnome.desktop.interface color-scheme prefer-dark
gsettings set org.gnome.shell favorite-apps "['org.gnome.Console.desktop']"
background=$(find /usr/share/backgrounds -type f \( -name '*.jxl' -o -name '*.png' -o -name '*.jpg' \) -print -quit)
if [[ -n "$background" ]]; then
 gsettings set org.gnome.desktop.background picture-uri "file://$background"
 gsettings set org.gnome.desktop.background picture-uri-dark "file://$background"
fi
pipewire >/run/pipewire.log 2>&1 &
wireplumber >/run/wireplumber.log 2>&1 &
xsetroot -solid '#20242b'
openbox >/run/openbox.log 2>&1 &
xterm -fa monospace -fs 22 -geometry 78x55+10+10 -title 'OP13 TOUCH DIAGNOSTICS' -e /usr/bin/bash /show-touch.sh >/run/touch-xterm.log 2>&1 &
(
 for ((j=0;j<150;j++)); do
  while IFS= read -r window; do xdotool windowraise "$window" 2>/dev/null; done < <(xdotool search --onlyvisible --name '^OP13 TOUCH DIAGNOSTICS$' 2>/dev/null)
  sleep 2
 done
) &

gnome-shell --wayland --devkit --devkit-args='--monitor-size=720x1500' --wayland-display=wayland-gnome >/run/gnome-shell.log 2>&1 &
gpid=$!
for ((i=0;i<120;i++)); do
 if ! kill -0 "$gpid" 2>/dev/null; then break; fi
 # Maximize the real GNOME devkit viewer on the phone's framebuffer.
 while IFS= read -r window; do
  xdotool windowsize "$window" 1440 3168 windowmove "$window" 0 0 windowactivate "$window" 2>/dev/null
 done < <(xdotool search --onlyvisible --class 'mutter-devkit|org.gnome.Mutter.Mdk|Mutter' 2>/dev/null)
 if [[ -S /run/user/0/wayland-gnome && ! -f /run/gnome-client-started ]]; then
  touch /run/gnome-client-started
  GDK_BACKEND=wayland WAYLAND_DISPLAY=wayland-gnome kgx -- /usr/bin/bash /show-touch.sh >/run/gnome-console.log 2>&1 &
 fi
 sleep 1
done
if kill -0 "$gpid" 2>/dev/null; then
 wait "$gpid"
else
 wait "$gpid"; status=$?
 printf 'GNOME Shell exited with status %s\n' "$status"
 xterm -fa monospace -fs 16 -geometry 78x65+0+0 -title 'GNOME startup diagnostics' -e /usr/bin/bash /show-diagnostics.sh &
 wait
fi
