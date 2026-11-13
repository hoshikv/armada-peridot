#!/usr/bin/bash
# Runs inside the reduced official Armada userspace, stored entirely in RAM.
export PATH=/usr/bin:/usr/sbin:/bin:/sbin HOME=/root SHELL=/usr/bin/bash
export LANG=C.UTF-8 XDG_RUNTIME_DIR=/run/user/0 DISPLAY=:0
export XDG_CONFIG_DIRS=/etc/xdg XDG_DATA_DIRS=/usr/local/share:/usr/share
export XDG_CURRENT_DESKTOP=KDE XDG_SESSION_DESKTOP=KDE XDG_SESSION_TYPE=x11
unset LIBGL_ALWAYS_SOFTWARE QT_QUICK_BACKEND
export GALLIUM_DRIVER=zink MESA_LOADER_DRIVER_OVERRIDE=zink LIBGL_KOPPER_DRI2=true
export MESA_VK_WSI_DEBUG=sw VK_DRIVER_FILES=/usr/share/vulkan/icd.d/freedreno_icd.aarch64.json
export LP_NUM_THREADS=1 QSG_RHI_BACKEND=opengl
export QSG_RENDER_LOOP=basic
export QT_QPA_PLATFORM=xcb NO_AT_BRIDGE=1
export QT_SCALE_FACTOR=1.25 QT_FONT_DPI=96 QT_IM_MODULE=qtvirtualkeyboard
unset QT_VIRTUALKEYBOARD_DESKTOP_DISABLE
unset QT_SCREEN_SCALE_FACTORS
unset WAYLAND_DISPLAY KWIN_WAYLAND_BACKEND
export KWIN_COMPOSE=N
unset GI_TYPELIB_PATH GDK_BACKEND GSK_RENDERER GNOME_SHELL_SESSION_MODE
mkdir -p /root/.config /root/.cache /var/lib/dbus /run/user/0
if /usr/bin/glxinfo -B >/run/armada-gpu-glx.log 2>&1 && grep -q 'Accelerated: yes' /run/armada-gpu-glx.log; then
 export KWIN_COMPOSE=N KWIN_X11_REFRESH_RATE=120000 KWIN_X11_FORCE_SOFTWARE_VSYNC=1 KWIN_X11_NO_SYNC_TO_VBLANK=1 KWIN_EXPLICIT_SYNC=0
 printf '[Compositing]\nEnabled=false\nBackend=OpenGL\n' >/root/.config/kwinrc
 printf 'GPU applications: Zink on Adreno 830; KWin compositor disabled for stability\n' >/run/armada-gpu-desktop.log
else
 unset MESA_LOADER_DRIVER_OVERRIDE LIBGL_KOPPER_DRI2 MESA_VK_WSI_DEBUG VK_DRIVER_FILES QSG_RHI_BACKEND
 export LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe QT_QUICK_BACKEND=software KWIN_COMPOSE=N
 printf '[Compositing]\nEnabled=false\n' >/root/.config/kwinrc
 printf 'GPU desktop probe failed; retained software fallback\n' >/run/armada-gpu-desktop.log
fi
kwriteconfig6 --file kdeglobals --group KScreen --key ScaleFactor 1.25
kwriteconfig6 --file kdeglobals --group KScreen --key ScreenScaleFactors "default=1.25;"
chmod 700 /run/user/0
if [[ -s /run/op13-machine-id ]]; then cp /run/op13-machine-id /etc/machine-id; fi
if [[ ! -s /etc/machine-id ]]; then rm -f /etc/machine-id; dbus-uuidgen --ensure=/etc/machine-id; fi
cp /etc/machine-id /var/lib/dbus/machine-id
bash /native-network-startup.sh
fc-cache -f >/run/armada-fonts.log 2>&1
exec dbus-run-session -- /usr/bin/bash /armada-desktop.sh
