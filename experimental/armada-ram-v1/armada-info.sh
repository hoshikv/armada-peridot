#!/usr/bin/bash
printf '\nArmada experimental RAM desktop — OnePlus 13\n\n'
cat /etc/os-release
printf '\nOfficial Armada userspace, custom kernel/boot path.\nSoftware rendering. Steam/Proton/FEX omitted from this RAM build.\nNo phone storage mounted. Reboot returns to Android.\n\nTouch bridge:\n'
cat /run/touch-bridge.log
printf '\n'
exec /usr/bin/bash --noprofile --norc -i
