#!/usr/bin/bash
printf 'GNOME startup failed. This terminal is a diagnostic display.\n\n'
for log in /run/gnome-shell.log /run/dbus-system.log /run/sysusers.log /run/gnome-console.log /run/pipewire.log; do
 printf '\n--- %s ---\n' "$log"
 tail -25 "$log"
done
exec /usr/bin/bash --noprofile --norc -i
