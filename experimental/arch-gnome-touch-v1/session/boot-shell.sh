#!/usr/bin/bash
export PATH=/usr/bin:/bin HOME=/root SHELL=/usr/bin/bash
export LANG=C.UTF-8 XDG_RUNTIME_DIR=/run/user/0
export XDG_CONFIG_DIRS=/etc/xdg XDG_DATA_DIRS=/usr/local/share:/usr/share
export XDG_CURRENT_DESKTOP=GNOME XDG_SESSION_DESKTOP=gnome
export LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe LP_NUM_THREADS=1
export GSK_RENDERER=cairo GTK_A11Y=none NO_AT_BRIDGE=1
mkdir -p /run/user/0 /run/dbus /dev/pts /dev/shm /tmp/.X11-unix /var/lib/dbus
chmod 700 /run/user/0
chmod 1777 /tmp /tmp/.X11-unix
systemd-sysusers >/run/sysusers.log 2>&1
chown dbus:dbus /run/dbus
chown root:dbus /usr/lib/dbus-daemon-launch-helper
chmod 4750 /usr/lib/dbus-daemon-launch-helper
mkdir -p /var/lib/AccountsService/users /var/lib/AccountsService/icons
dbus-uuidgen --ensure=/etc/machine-id
dbus-uuidgen --ensure=/var/lib/dbus/machine-id
dbus-daemon --system --fork --nopidfile --nosyslog 2>/run/dbus-system.log
glib-compile-schemas /usr/share/glib-2.0/schemas >/run/schemas.log 2>&1
gio-querymodules /usr/lib/gio/modules >/run/gio-cache.log 2>&1
for query in /usr/bin/gdk-pixbuf-query-loaders /usr/lib/gdk-pixbuf-2.0/gdk-pixbuf-query-loaders; do
 if [[ -x "$query" ]]; then "$query" --update-cache >/run/pixbuf-cache.log 2>&1; break; fi
done
fc-cache -f >/run/font-cache.log 2>&1
bash /touch-usb.sh >/run/touch-usb.log 2>&1
insmod /usr/lib/modules/7.3.0-1-aarch64-ARCH/kernel/drivers/input/misc/uinput.ko >/run/uinput.log 2>&1
cmdline=$(</proc/cmdline)
if [[ " $cmdline " == *" op13_touch=1 "* ]]; then
 /usr/bin/op13-touch --firmware-lease >/run/touch-bridge.log 2>&1 &
 touchpid=$!
 for ((i=0;i<50;i++)); do
  [[ $(</run/touch-bridge.log) == *'TOUCH READY'* ]] && break
  kill -0 "$touchpid" 2>/dev/null || break
  sleep 0.1
 done
else
 printf 'REFUSED: op13_touch=1 missing from kernel command line\n%s\n' "$cmdline" > /run/touch-bridge.log
fi
python /touch-input.py >/run/touch-input.log 2>&1
cat /run/touch-bridge.log /run/touch-input.log
printf '\nArch GNOME RAM boot: starting framebuffer Xorg.\n'
ls -l /dev/fb* /dev/dri/* 2>/dev/null
Xorg :0 -config /etc/X11/dodge-fbdev.conf -logfile /run/Xorg.0.log -nolisten tcp -ac -noreset -novtswitch -keeptty vt1 >/run/xorg-launch.log 2>&1 &
xpid=$!
export DISPLAY=:0
for ((i=0;i<40;i++)); do
 if xdpyinfo >/run/xdpyinfo.txt 2>&1; then break; fi
 if ! kill -0 "$xpid" 2>/dev/null; then break; fi
 sleep 1
done
if xdpyinfo >/run/xdpyinfo.txt 2>&1; then
 printf 'Framebuffer Xorg ready. Starting GNOME Shell devkit.\n'
 dbus-run-session -- /usr/bin/bash /gnome-session.sh >/run/gnome-session.log 2>&1
else
 printf '\nXorg failed; this is not a GNOME desktop boot.\n'
 tail -45 /run/Xorg.0.log /run/xorg-launch.log
fi
printf '\nGNOME test ended. RAM shell remains; no phone disks mounted.\n'
exec /usr/bin/bash --noprofile --norc -i
