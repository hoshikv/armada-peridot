#!/usr/bin/bash
exec >>/run/hardware-startup.log 2>&1
if [[ ! -d /sys/module/qcom_pon ]]; then insmod /hardware-modules/qcom_pon.ko || true; fi
if [[ ! -d /sys/module/gpio_keys ]]; then insmod /hardware-modules/gpio_keys.ko || true; fi
if [[ ! -d /sys/module/ecc ]]; then insmod /hardware-modules/ecc.ko || true; fi
if [[ ! -d /sys/module/ecdh_generic ]]; then insmod /hardware-modules/ecdh_generic.ko || true; fi
if [[ ! -d /sys/module/rfkill ]]; then insmod /hardware-modules/rfkill.ko || true; fi
if [[ ! -d /sys/module/bluetooth ]]; then insmod /hardware-modules/bluetooth.ko || true; fi
if [[ ! -d /sys/module/btintel ]]; then insmod /hardware-modules/btintel.ko || true; fi
if [[ ! -d /sys/module/btbcm ]]; then insmod /hardware-modules/btbcm.ko || true; fi
if [[ ! -d /sys/module/btrtl ]]; then insmod /hardware-modules/btrtl.ko || true; fi
if [[ ! -d /sys/module/btqca ]]; then insmod /hardware-modules/btqca.ko || true; fi
if [[ ! -d /sys/module/hci_uart ]]; then insmod /hardware-modules/hci_uart.ko || true; fi
if [[ ! -d /sys/module/rfcomm ]]; then insmod /hardware-modules/rfcomm.ko || true; fi
if [[ ! -d /sys/module/bnep ]]; then insmod /hardware-modules/bnep.ko || true; fi
if [[ ! -d /sys/module/hidp ]]; then insmod /hardware-modules/hidp.ko || true; fi
if [[ ! -d /sys/module/uhid ]]; then insmod /hardware-modules/uhid.ko || true; fi
cat /proc/bus/input/devices
