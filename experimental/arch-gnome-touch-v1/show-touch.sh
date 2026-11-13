#!/usr/bin/bash
while true; do
 printf '\033[2J\033[H'
 printf 'ONEPLUS 13 TOUCH DIAGNOSTICS\nPlease report the REFUSED / probe / LBP / READY lines.\n\n'
 printf 'Module loading:\n'; cat /run/uinput.log 2>/dev/null
 printf '\nBridge process:\n'; pgrep -af op13-touch
 printf '\nBridge log:\n'; tail -22 /run/touch-bridge.log 2>/dev/null
 printf '\nDetected input:\n'; cat /run/touch-input.json /run/touch-input.log 2>/dev/null | tail -20
 printf '\nRecent kernel errors:\n'; dmesg | tail -5
 sleep 3
done
