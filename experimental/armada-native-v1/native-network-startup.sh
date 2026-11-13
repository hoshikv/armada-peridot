#!/usr/bin/bash
# Inside the RAM Armada chroot. The system D-Bus and /run are shared with host.
exec >>/run/native-network-startup.log 2>&1
if [[ ! -s /etc/machine-id ]]; then
 rm -f /etc/machine-id
 dbus-uuidgen --ensure=/etc/machine-id || exit 1
fi
mkdir -p /var/lib/dbus /var/lib/NetworkManager /run/NetworkManager /etc/NetworkManager/conf.d
cp /etc/machine-id /var/lib/dbus/machine-id
export DBUS_SYSTEM_BUS_ADDRESS=unix:path=/run/dbus/system_bus_socket
export SYSTEMD_IN_CHROOT=0
if [[ -L /etc/resolv.conf ]]; then rm -f /etc/resolv.conf; fi
touch /etc/resolv.conf
cat >/etc/NetworkManager/conf.d/99-op13-ram.conf <<'EOF'
[main]
dhcp=internal
dns=default
rc-manager=file
[logging]
backend=debug
level=DEBUG
domains=CORE,PLATFORM,WIFI,SUPPLICANT,RFKILL
[device]
wifi.scan-rand-mac-address=no
EOF
wpid='';npid='';upid=''
for process in /proc/[0-9]*; do
 [[ -r "$process/comm" ]] || continue
 IFS= read -r name <"$process/comm" || continue
 [[ "$name" == wpa_supplicant ]] && wpid=${process##*/}
 [[ "$name" == NetworkManager ]] && npid=${process##*/}
 [[ "$name" == systemd-udevd ]] && upid=${process##*/}
done
if [[ -z "$upid" ]]; then
 /usr/lib/systemd/systemd-udevd --daemon || true
fi
/usr/bin/udevadm trigger --subsystem-match=net --action=add || true
/usr/bin/udevadm settle --timeout=3 || true
if [[ -z "$wpid" ]]; then
 /usr/sbin/wpa_supplicant -u -B -f /run/op13-wpa.log || true
fi
if [[ -z "$npid" ]]; then
 rm -f /run/NetworkManager/NetworkManager.pid
 /usr/sbin/NetworkManager --debug --no-daemon --log-level=DEBUG >/run/native-networkmanager.log 2>&1 &
 sleep 2
fi
