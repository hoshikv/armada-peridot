# WiFi/BT Support for Peridot (SM8635 / WCN6750)

Adapted from armada-dodge WiFi/BT documentation for OnePlus 13 (WCN7860) and xnu-kernel-peridot.

## Hardware Overview

| Component | Controller | Interface | Details |
|-----------|------------|-----------|---------|
| WiFi | WCN6750 | PCIe Gen 3 x1 | ath11k driver, WPSS DSP at 0x9BB00000 (25MB) |
| Bluetooth | WCN6750 | H4 UART (QUPv3 SE2) | 3 Mbps baudrate, QUPv3 SE2 @ 0x00888000 |

## WiFi (ath11k)

### Key Addresses
- **WPSS Memory**: `0x9BB00000` (25MB, reserved)
- **PCIe RC**: `0x01C00000` (PCIe_0)
- **IRQ**: GIC_SPI 160-163

### Firmware (from `/vendor/firmware_mnt/image`)
```
ath11k/WCN6750/hw2.0/
├── firmware.bin      # Main firmware
├── board.bin         # Board data (calibration)
├── board-2.bin       # Board data v2
└── notice.txt        # License
```

### BDF (Board Data File)
- Peridot uses **`n16t`** BDF (from xnu-kernel-peridot)
- Must match the exact board data for regulatory compliance

### PCIe Link
- Gen 3 x1 (8 GT/s)
- ASPM L1/L1.2 support
- MSI/MSI-X interrupts

### Driver
Standard Linux `ath11k` driver (in `drivers/net/wireless/ath/ath11k/`)

Kernel config:
```kconfig
CONFIG_ATH11K=m
CONFIG_ATH11K_PCI=m
CONFIG_ATH11K_DEBUG=y
CONFIG_ATH11K_DEBUGFS=y
CONFIG_ATH11K_SPECTRAL=y
```

## Bluetooth (H4 UART)

### Key Addresses
- **QUPv3 SE2**: `0x00888000` (size 0x10000)
- **IRQ**: GIC_SPI 180
- **Baudrate**: 3 Mbps (WCN6750 peripheral baudrate)

### Firmware
```
qca/
├── btfw32.tlv    # Bluetooth firmware
├── btfw32.cfg    # Configuration
└── notice.txt    # License
```

### HCI Transport
- H4 (4-wire UART: TX, RX, RTS, CTS)
- Flow control enabled
- Wake host via GPIO

### GPIOs
| Signal | GPIO | Description |
|--------|------|-------------|
| TX | 20 | QUPv3 SE2 TX |
| RX | 21 | QUPv3 SE2 RX |
| SHUTDOWN | 131 | Active low, BT reset |
| WAKE_HOST | 132 | Active high, BT wake |

### Driver
Standard Linux `hci_uart` with `qca` protocol:

Kernel config:
```kconfig
CONFIG_BT_HCIUART=m
CONFIG_BT_HCIUART_H4=y
CONFIG_BT_HCIUART_QCA=y
CONFIG_BT_QCA=m
```

## Power Management (RPMh)

WCN6750 power rails controlled via RPMh:

| Rail | RPMH ID | Description |
|------|---------|-------------|
| CX | `RPMH_WIFI_CX` | Always-on domain |
| MX | `RPMH_WIFI_MX` | Main domain |
| XO | `RPMH_WIFI_XO` | Crystal oscillator |

## Device Tree

See `experimental/peridot-wifi-bt-v1/sm8635-wifi-bt.dtsi` for complete DT.

### Key Nodes
- `pcie_wifi` - PCIe root complex for WiFi
- `wifi` - WCN6750 WiFi device (ath11k)
- `bluetooth` - WCN6750 BT device (H4 UART)
- `qupv3_0_geni_se` - QUPv3 SE2 for BT UART
- RPMh regulators for power rails
- Reserved memory for WPSS

## Firmware Installation

```bash
# Create firmware directory
mkdir -p /lib/firmware/ath11k/WCN6750/hw2.0
mkdir -p /lib/firmware/qca

# Copy from device (adb root required)
adb pull /vendor/firmware_mnt/image/ath11k/WCN6750/hw2.0/firmware.bin /lib/firmware/ath11k/WCN6750/hw2.0/
adb pull /vendor/firmware_mnt/image/ath11k/WCN6750/hw2.0/board.bin /lib/firmware/ath11k/WCN6750/hw2.0/
adb pull /vendor/firmware_mnt/image/ath11k/WCN6750/hw2.0/board-2.bin /lib/firmware/ath11k/WCN6750/hw2.0/
adb pull /vendor/firmware_mnt/image/qca/btfw32.tlv /lib/firmware/qca/
adb pull /vendor/firmware_mnt/image/qca/btfw32.cfg /lib/firmware/qca/
```

## Debugging

### WiFi
```bash
# Driver status
dmesg | grep -i ath11k
ls /sys/kernel/debug/ath11k/

# Interface
ip link show wlan0
iw dev wlan0 info

# Firmware version
cat /sys/kernel/debug/ath11k/*/fw_version
```

### Bluetooth
```bash
# HCI device
hciconfig -a
btmgmt info

# UART
cat /proc/tty/driver/serial | grep qcom

# Firmware
dmesg | grep -i -e bluetooth -e hci -e qca
```

### PCIe Link
```bash
lspci -vv -d 17cb:  # Qualcomm vendor ID
cat /sys/bus/pci/devices/*/link_cap
cat /sys/bus/pci/devices/*/link_sta
```

## Known Issues / TODO

- [ ] Verify exact PCIe RC address for Peridot (may be PCIe_1 not PCIe_0)
- [ ] Confirm BDF `n16t` is correct for all Peridot variants
- [ ] Test WiFi 6E/7 features (6 GHz band)
- [ ] Implement BT coexistence (WiFi/BT antenna sharing)
- [ ] Verify RPMH rail IDs for WCN6750 on SM8635
- [ ] Test Bluetooth LE audio (LC3 codec)
- [ ] Add regulatory database for China/India/US/EU variants
- [ ] Implement firmware crash dump collection