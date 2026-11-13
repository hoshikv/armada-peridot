#!/usr/bin/bash
# Runs inside the reduced official Armada userspace, stored entirely in RAM.
export PATH=/usr/bin:/usr/sbin:/bin:/sbin HOME=/root SHELL=/usr/bin/bash
export LANG=C.UTF-8 XDG_RUNTIME_DIR=/run/user/0 DISPLAY=:0
export XDG_CONFIG_DIRS=/etc/xdg XDG_DATA_DIRS=/usr/local/share:/usr/share
export XDG_CURRENT_DESKTOP=KDE XDG_SESSION_DESKTOP=KDE XDG_SESSION_TYPE=x11
export LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe LP_NUM_THREADS=1
export QT_QUICK_BACKEND=software QSG_RENDER_LOOP=basic
export QT_QPA_PLATFORM=xcb NO_AT_BRIDGE=1
unset WAYLAND_DISPLAY KWIN_WAYLAND_BACKEND
export KWIN_COMPOSE=N
unset GI_TYPELIB_PATH GDK_BACKEND GSK_RENDERER GNOME_SHELL_SESSION_MODE
mkdir -p /root/.config /root/.cache /var/lib/dbus /run/user/0
printf '[Compositing]\nEnabled=false\n' >/root/.config/kwinrc
chmod 700 /run/user/0
dbus-uuidgen --ensure=/etc/machine-id
dbus-uuidgen --ensure=/var/lib/dbus/machine-id
fc-cache -f >/run/armada-fonts.log 2>&1
exec dbus-run-session -- /usr/bin/bash /armada-desktop.sh
