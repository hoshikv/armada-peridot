# Armada-Dodge Peridot Build Makefile
# Helper targets for building kernel modules and components

# Toolchain
export LLVM ?= /opt/homebrew/opt/llvm/bin
export LD ?= /opt/homebrew/bin/ld.lld
export CROSS_COMPILE ?= aarch64-linux-gnu-
export ARCH = arm64

# Kernel headers (must match running kernel)
KERNEL_HEADERS ?= $(WORKSPACE)/kernel-headers

# Module directories
MSM_DRM_DIR := source/linux/drivers/gpu/drm/msm
ATH11K_DIR := source/linux/drivers/net/wireless/ath/ath11k
TOUCH_DIR := source/linux/drivers/input/touchscreen
BT_DIR := source/linux/drivers/bluetooth
PROVIDERS_DIR := source/modules/providers

# Build flags
KBUILD_FLAGS := ARCH=$(ARCH) CROSS_COMPILE=$(CROSS_COMPILE) LLVM=$(LLVM) LD=$(LD) \
                KCPPFLAGS="-Wno-error=unused-variable"

.PHONY: all modules msm-drm ath11k touch bt providers clean help

all: modules

modules: msm-drm ath11k touch bt providers

msm-drm:
	$(MAKE) -C $(KERNEL_HEADERS) M=$(MSM_DRM_DIR) $(KBUILD_FLAGS) modules

ath11k:
	$(MAKE) -C $(KERNEL_HEADERS) M=$(ATH11K_DIR) $(KBUILD_FLAGS) modules

touch:
	$(MAKE) -C $(KERNEL_HEADERS) M=$(TOUCH_DIR) $(KBUILD_FLAGS) modules

bt:
	$(MAKE) -C $(KERNEL_HEADERS) M=$(BT_DIR) $(KBUILD_FLAGS) modules

providers:
	$(MAKE) -C $(KERNEL_HEADERS) M=$(PROVIDERS_DIR) $(KBUILD_FLAGS) modules

# Install modules to workspace
install-modules: modules
	$(MAKE) -C $(KERNEL_HEADERS) M=$(MSM_DRM_DIR) $(KBUILD_FLAGS) INSTALL_MOD_PATH=$(WORKSPACE)/modules modules_install
	$(MAKE) -C $(KERNEL_HEADERS) M=$(ATH11K_DIR) $(KBUILD_FLAGS) INSTALL_MOD_PATH=$(WORKSPACE)/modules modules_install
	$(MAKE) -C $(KERNEL_HEADERS) M=$(TOUCH_DIR) $(KBUILD_FLAGS) INSTALL_MOD_PATH=$(WORKSPACE)/modules modules_install
	$(MAKE) -C $(KERNEL_HEADERS) M=$(BT_DIR) $(KBUILD_FLAGS) INSTALL_MOD_PATH=$(WORKSPACE)/modules modules_install
	$(MAKE) -C $(KERNEL_HEADERS) M=$(PROVIDERS_DIR) $(KBUILD_FLAGS) INSTALL_MOD_PATH=$(WORKSPACE)/modules modules_install

# DTB
dtb:
	dtc -I dts -O dtb -o $(WORKSPACE)/peridot.dtb \
		source/linux/arch/arm64/boot/dts/qcom/sm8635-peridot.dts

# Clean
clean:
	$(MAKE) -C $(KERNEL_HEADERS) M=$(MSM_DRM_DIR) $(KBUILD_FLAGS) clean
	$(MAKE) -C $(KERNEL_HEADERS) M=$(ATH11K_DIR) $(KBUILD_FLAGS) clean
	$(MAKE) -C $(KERNEL_HEADERS) M=$(TOUCH_DIR) $(KBUILD_FLAGS) clean
	$(MAKE) -C $(KERNEL_HEADERS) M=$(BT_DIR) $(KBUILD_FLAGS) clean
	$(MAKE) -C $(KERNEL_HEADERS) M=$(PROVIDERS_DIR) $(KBUILD_FLAGS) clean

help:
	@echo "Armada-Dodge Peridot Makefile"
	@echo ""
	@echo "Variables:"
	@echo "  WORKSPACE      - Workspace directory (required)"
	@echo "  KERNEL_HEADERS - Kernel headers path (default: \$(WORKSPACE)/kernel-headers)"
	@echo "  LLVM           - LLVM bin path (default: /opt/homebrew/opt/llvm/bin)"
	@echo "  LD             - LLD path (default: /opt/homebrew/bin/ld.lld)"
	@echo "  CROSS_COMPILE  - Cross compiler prefix (default: aarch64-linux-gnu-)"
	@echo ""
	@echo "Targets:"
	@echo "  all            - Build all modules"
	@echo "  modules        - Build all kernel modules"
	@echo "  msm-drm        - Build MSM DRM/GPU driver"
	@echo "  ath11k         - Build ath11k WiFi driver"
	@echo "  touch          - Build Goodix touchscreen driver"
	@echo "  bt             - Build Bluetooth driver"
	@echo "  providers      - Build clock/power provider modules"
	@echo "  install-modules- Install modules to WORKSPACE/modules"
	@echo "  dtb            - Compile device tree"
	@echo "  clean          - Clean all module builds"
	@echo "  help           - Show this help"