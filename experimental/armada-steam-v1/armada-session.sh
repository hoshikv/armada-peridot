#!/usr/bin/bash
export PATH=/usr/bin:/usr/sbin:/bin:/sbin HOME=/root SHELL=/usr/bin/bash LANG=C.UTF-8
export XDG_RUNTIME_DIR=/run/user/0 XDG_CONFIG_DIRS=/etc/xdg XDG_DATA_DIRS=/usr/local/share:/usr/share
export XDG_CURRENT_DESKTOP=KDE XDG_SESSION_DESKTOP=KDE XDG_SESSION_TYPE=wayland
unset DISPLAY WAYLAND_DISPLAY LIBGL_ALWAYS_SOFTWARE GALLIUM_DRIVER QT_QUICK_BACKEND MESA_LOADER_DRIVER_OVERRIDE LIBGL_KOPPER_DRI2 MESA_VK_WSI_DEBUG
unset QT_SCALE_FACTOR QT_SCREEN_SCALE_FACTORS QT_FONT_DPI QT_IM_MODULE KWIN_COMPOSE GDK_BACKEND GSK_RENDERER
export VK_DRIVER_FILES=/usr/share/vulkan/icd.d/freedreno_icd.aarch64.json
export SYSTEMD_IN_CHROOT=0
export QT_QPA_PLATFORM=wayland LP_NUM_THREADS=1 NO_AT_BRIDGE=1
mkdir -p /root/.config /root/.cache /run/user/0 /var/lib/dbus
chmod 700 /run/user/0
cp /run/op13-machine-id /etc/machine-id
cp /etc/machine-id /var/lib/dbus/machine-id
bash /native-network-startup.sh
bash /bluetooth-startup.sh &
udevadm trigger --subsystem-match=input --action=add
udevadm trigger --subsystem-match=drm --action=add
udevadm settle --timeout=5
libinput list-devices >/run/armada-input.log 2>&1
udevadm info --export-db >/run/armada-udev.log 2>&1
printf '[Wayland]
VirtualKeyboardEnabled=true
' >/root/.config/kwinrc
exec dbus-run-session -- kwin_wayland --drm --xwayland --no-lockscreen --inputmethod /usr/bin/plasma-keyboard --exit-with-session /armada-desktop.sh
