#!/usr/bin/bash
exec >>/run/steam-prepare.log 2>&1
mkdir -p /var/home/armada /run/user/1000
chown -R armada:armada /var/home/armada
chown armada:armada /run/user/1000
chmod 700 /run/user/1000
for node in /dev/dri/renderD*; do setfacl -m u:1000:rw "$node"; done
xhost +SI:localuser:armada
printf '%s' "$DISPLAY" >/run/steam-display
printf 'Steam UI ready for launch; waiting for a network connection.\n'
for ((i=0;i<1800;i++)); do
 if nmcli -t -f TYPE,STATE device status | grep -q '^wifi:connected$'; then
  exec runuser -u armada -- env DISPLAY="$DISPLAY" /usr/bin/bash /steam-session.sh
 fi
 sleep 1
done
printf 'Network wait timed out; Steam can be launched from the desktop icon.\n'
