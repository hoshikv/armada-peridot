#!/usr/bin/bash
# Native display experiment; independent USB recovery service starts first.
exec >>/run/native-startup.log 2>&1
printf 'Native SM8750 render-node probe; phone storage is not mounted\n'
insmod /native-modules/drm_exec.ko
insmod /native-modules/drm_gpuvm.ko
insmod /native-modules/gpu-sched.ko
insmod /native-modules/drm_client_lib.ko
insmod /native-modules/mdt_loader.ko
insmod /native-modules/ocmem.ko
insmod /native-modules/ubwc_config.ko
insmod /native-modules/gpucc-sm8750.ko
insmod /native-modules/gxclkctl-kaanapali.ko
insmod /native-modules/dispcc-sm8750.ko
insmod /native-modules/panel-aa569-p-3-a0019-dsc.ko
insmod /native-modules/msm.ko separate_gpu_kms=1
for name in rfkill cfg80211 libarc4 mac80211 qmi_helpers mhi qrtr qrtr-mhi; do
 insmod "/native-modules/$name.ko"
done
insmod /native-modules/pwrseq-qcom-wcn.ko
insmod /native-modules/pci-pwrctrl-pwrseq.ko
insmod /native-modules/ath12k.ko
insmod /native-modules/ath12k_wifi7.ko
sleep 2
cat /sys/kernel/debug/devices_deferred
ls -l /dev/dri
cat /sys/class/drm/card*-*/status 2>/dev/null
touch /run/native-ready
printf '\nNative probe finished; desktop keeps its current software configuration.\n'

bash /load-modules.sh
python /buttons.py >/run/buttons.log 2>&1 &
