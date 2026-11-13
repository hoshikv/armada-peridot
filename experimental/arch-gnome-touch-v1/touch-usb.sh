#!/usr/bin/bash
set -e
# Diagnostic-only USB serial gadget. All configuration is in virtual filesystems.
mount -t configfs configfs /sys/kernel/config 2>/dev/null || true
modules=/usr/lib/modules/7.3.0-1-aarch64-ARCH/kernel/drivers
for module in usb/gadget/libcomposite.ko usb/gadget/function/u_serial.ko usb/gadget/function/usb_f_acm.ko; do
 insmod "$modules/$module" || exit 1
done
udc=$(find /sys/class/udc -mindepth 1 -maxdepth 1 -printf '%f\n' | head -1)
if [[ -z "$udc" ]]; then echo 'No USB device controller exposed by Linux'; exit 0; fi
g=/sys/kernel/config/usb_gadget/op13_ram_diag
mkdir -p "$g"
printf '0x1d6b' > "$g/idVendor"
printf '0x0104' > "$g/idProduct"
mkdir -p "$g/strings/0x409"
printf 'OP13ARCHRAM' > "$g/strings/0x409/serialnumber"
printf 'Arch RAM diagnostics' > "$g/strings/0x409/product"
mkdir -p "$g/configs/c.1" "$g/functions/acm.usb0"
ln -s "$g/functions/acm.usb0" "$g/configs/c.1/"
printf '%s' "$udc" > "$g/UDC"
echo "USB serial diagnostics enabled on $udc"
(
 for ((i=0;i<30;i++)); do [[ -c /dev/ttyGS0 ]] && break; sleep 1; done
 {
  printf '\nOP13 GNOME RAM TOUCH DIAGNOSTICS\n'
  uname -a
  cat /proc/bus/input/devices
  dmesg | tail -100
  while true; do
   printf '\n--- touch status ---\n'
   cat /run/touch-bridge.log /run/touch-input.json 2>/dev/null
   tail -15 /run/gnome-shell.log 2>/dev/null
   sleep 4
  done
 } > /dev/ttyGS0 2>&1
) &
