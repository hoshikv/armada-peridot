#!/usr/bin/bash
for path in dev proc sys run tmp; do
 mkdir -p "/armada/$path"
 mount --rbind "/$path" "/armada/$path" || exit 1
 mount --make-rslave "/armada/$path"
done
exec chroot /armada /usr/bin/bash /armada-session.sh
