#!/usr/bin/bash
# Matching Linux 7.3 modules, RAM configfs gadget, no disk or partition operations.
mkdir -p /run
exec >>/run/usb-startup.log 2>&1
printf 'OP13 USB recovery startup\n'
modules=/usb-modules
for name in tcsrcc-sm8750 gcc-sm8750 pinctrl-sm8750 icc-sm8750 phy-qcom-eusb2-repeater phy-qcom-m31-eusb2; do
 printf '\nLoading %s\n' "$name"
 insmod "$modules/$name.ko" || printf 'Module load failed: %s\n' "$name"
done
mount -t debugfs debugfs /sys/kernel/debug 2>/dev/null || true
for ((i=0;i<30;i++)); do
 udc=''
 for candidate in /sys/class/udc/*; do [[ -e "$candidate" ]] && udc=${candidate##*/}; done
 [[ -n "$udc" ]] && break
 sleep 1
done
cat /sys/kernel/debug/devices_deferred 2>/dev/null
dmesg | tail -100
if [[ -z "$udc" ]]; then printf '\nUSB CONTROL FAILED: no UDC; inspect this log\n'; exit 1; fi
mount -t configfs configfs /sys/kernel/config 2>/dev/null || true
km=/usr/lib/modules/7.3.0-1-aarch64-ARCH/kernel/drivers/usb/gadget
for name in libcomposite function/u_serial function/usb_f_acm; do insmod "$km/$name.ko" || true; done
g=/sys/kernel/config/usb_gadget/op13_ram_control
mkdir -p "$g/strings/0x409" "$g/configs/c.1" "$g/functions/acm.usb0"
printf '0x1d6b' > "$g/idVendor"
printf '0x0104' > "$g/idProduct"
printf 'OP13RAMCONTROL' > "$g/strings/0x409/serialnumber"
printf 'OnePlus RAM recovery' > "$g/strings/0x409/product"
ln -s "$g/functions/acm.usb0" "$g/configs/c.1/"
if ! printf '%s' "$udc" > "$g/UDC"; then printf 'USB CONTROL FAILED: bind failed\n'; exit 1; fi
python /usb-control.py >/run/usb-control.log 2>&1 &
printf '\nUSB CONTROL READY: %s, serial OP13RAMCONTROL\n' "$udc"
