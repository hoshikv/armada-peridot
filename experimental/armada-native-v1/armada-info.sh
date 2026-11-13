#!/usr/bin/bash
printf '\nArmada experimental RAM desktop — OnePlus 13\n\n'
cat /etc/os-release
printf '\nOfficial Armada userspace, custom kernel/boot path.\nGPU path: Zink on Adreno 830, with framebuffer presentation.\nSteam/Proton/FEX omitted from this RAM build.\nNo phone storage mounted. Reboot returns to Android.\n\nTouch bridge:\n'
cat /run/armada-gpu-desktop.log
grep -E 'Accelerated:|OpenGL renderer string' /run/armada-gpu-glx.log
tail -12 /run/touch-bridge.log
printf '\n'
exec /usr/bin/bash --noprofile --norc -i
