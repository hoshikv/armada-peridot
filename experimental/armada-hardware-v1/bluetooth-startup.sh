#!/usr/bin/bash
# Inside Armada, all address/configuration files exist only in RAM.
exec >>/run/bluetooth-startup.log 2>&1
export DBUS_SYSTEM_BUS_ADDRESS=unix:path=/run/dbus/system_bus_socket
mkdir -p /var/lib/bluetooth /etc/bluetooth
for ((i=0;i<60;i++)); do
 [[ -d /sys/class/bluetooth/hci0 ]] && break
 sleep 0.5
done
if [[ ! -d /sys/class/bluetooth/hci0 ]]; then echo 'NO BLUETOOTH CONTROLLER'; exit 1; fi
/usr/libexec/bluetooth/bluetoothd --nodetach --debug >/run/bluetoothd.log 2>&1 &
for ((i=0;i<60;i++)); do
 info=$(btmgmt info 2>&1)
 if [[ "$info" == *'Primary controller'* ]]; then break; fi
 config=$(btmgmt -i 0 config 2>&1)
 if [[ "$config" == *'missing options:'*'public-address'* ]]; then
  addr=$(python3 -c 'import secrets;print("02:"+":".join(f"{x:02X}" for x in secrets.token_bytes(5)))')
  btmgmt -i 0 public-addr "$addr"
 fi
 sleep 0.5
done
btmgmt info
bluetoothctl power on
bluetoothctl show
