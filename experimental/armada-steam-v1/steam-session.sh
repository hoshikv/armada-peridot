#!/usr/bin/bash
# Runs as the existing unprivileged armada account. All home/cache files are RAM.
export HOME=/var/home/armada USER=armada LOGNAME=armada XDG_RUNTIME_DIR=/run/user/1000
export QT_QPA_PLATFORM=xcb SDL_VIDEODRIVER=x11
export XDG_SESSION_TYPE=x11 XDG_CURRENT_DESKTOP=KDE LANG=C.UTF-8
export STEAM_ROOT="$HOME/.local/share/Steam"
unset WAYLAND_DISPLAY XAUTHORITY QT_SCALE_FACTOR QT_IM_MODULE GALLIUM_DRIVER MESA_LOADER_DRIVER_OVERRIDE LIBGL_ALWAYS_SOFTWARE MESA_VK_WSI_DEBUG
export VK_DRIVER_FILES=/usr/share/vulkan/icd.d/freedreno_icd.aarch64.json
exec dbus-run-session -- /usr/libexec/armada/launch-steam --desktop -gamepadui -skipinitialbootstrap -noverifyfiles -norepairfiles "$@"
