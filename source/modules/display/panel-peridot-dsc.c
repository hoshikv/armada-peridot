/*
 * Xiaomi Peridot (POCO F6 / Redmi Turbo 3) Display Panel Driver
 *
 * Panel: 1220 x 2712 @ 120 Hz, MIPI DSI, DSC compression
 * Likely Samsung E6 or BOE panel (exact model TBD)
 *
 * Adapted from armada-dodge panel-aa569-p-3-a0019-dsc.c (OnePlus 13)
 * and xnu-kernel-peridot display bringup.
 */

#include <linux/delay.h>
#include <linux/gpio/consumer.h>
#include <linux/module.h>
#include <linux/of_device.h>
#include <linux/regulator/consumer.h>
#include <video/mipi_display.h>
#include <drm/drm_mipi_dsi.h>
#include <drm/drm_panel.h>
#include <drm/drm_dsc.h>

/* Panel timing (1220 x 2712 @ 120 Hz) */
#define PERIDOT_HACTIVE		1220
#define PERIDOT_VACTIVE		2712
#define PERIDOT_HFP		80
#define PERIDOT_HSA		8
#define PERIDOT_HBP		80
#define PERIDOT_VFP		24
#define PERIDOT_VSA		4
#define PERIDOT_VBP		16
#define PERIDOT_VREFRESH	120
#define PERIDOT_PIXCLK		432000000  /* ~432 MHz pixel clock with DSC */

/* DSC Configuration */
#define PERIDOT_DSC_SLICE_COUNT		2
#define PERIDOT_DSC_SLICE_HEIGHT	8
#define PERIDOT_DSC_BITS_PER_PIXEL	128  /* 10 bpc * 3 components * 4/3 compression */
#define PERIDOT_DSC_PIC_WIDTH		PERIDOT_HACTIVE
#define PERIDOT_DSC_PIC_HEIGHT		PERIDOT_VACTIVE

/* Panel commands (typical DCS + manufacturer specific) */
static const struct mipi_dsi_cmd peridot_init_cmds[] = {
	/* Exit sleep mode */
	{ MIPI_DCS_EXIT_SLEEP_MODE, 0, NULL },
	{ MIPI_DCS_SET_DISPLAY_ON, 0, NULL },

	/* TODO: Add panel-specific initialization sequence */
	/* This needs to be obtained from Xiaomi kernel source or panel datasheet */
	/* Example placeholders: */
	/* { 0xFF, 3, (u8[]){0x98, 0x81, 0x03} },  // Command page unlock */
	/* { 0xC0, 1, (u8[]){0x0E} },               // Power control */
	/* ... */
};

static const struct mipi_dsi_cmd peridot_exit_cmds[] = {
	{ MIPI_DCS_SET_DISPLAY_OFF, 0, NULL },
	{ MIPI_DCS_ENTER_SLEEP_MODE, 0, NULL },
};

/* DSC PPS (Picture Parameter Set) - will be filled at runtime */
static struct drm_dsc_pict_parameter_set peridot_dsc_pps;

struct peridot_panel {
	struct drm_panel base;
	struct mipi_dsi_device *dsi;
	struct gpio_desc *reset_gpio;
	struct regulator_bulk_data supplies[3];
	bool prepared;
	bool enabled;
};

static inline struct peridot_panel *to_peridot_panel(struct drm_panel *panel)
{
	return container_of(panel, struct peridot_panel, base);
}

static int peridot_panel_reset(struct peridot_panel *ctx)
{
	if (!ctx->reset_gpio)
		return 0;

	gpiod_set_value_cansleep(ctx->reset_gpio, 1);
	usleep_range(1000, 2000);
	gpiod_set_value_cansleep(ctx->reset_gpio, 0);
	usleep_range(5000, 6000);
	gpiod_set_value_cansleep(ctx->reset_gpio, 1);
	usleep_range(20000, 21000);

	return 0;
}

static int peridot_panel_power_on(struct peridot_panel *ctx)
{
	int ret;

	/* Enable regulators: VDDI (1.8V), VDDA (3.3V), VDD (varies) */
	ret = regulator_bulk_enable(ARRAY_SIZE(ctx->supplies), ctx->supplies);
	if (ret) {
		dev_err(ctx->base.dev, "failed to enable regulators: %d\n", ret);
		return ret;
	}

	usleep_range(10000, 11000);

	/* Hardware reset */
	peridot_panel_reset(ctx);

	return 0;
}

static int peridot_panel_power_off(struct peridot_panel *ctx)
{
	regulator_bulk_disable(ARRAY_SIZE(ctx->supplies), ctx->supplies);
	return 0;
}

static int peridot_panel_init_sequence(struct peridot_panel *ctx)
{
	struct mipi_dsi_device *dsi = ctx->dsi;
	int ret, i;

	/* Send initialization commands */
	for (i = 0; i < ARRAY_SIZE(peridot_init_cmds); i++) {
		const struct mipi_dsi_cmd *cmd = &peridot_init_cmds[i];

		ret = mipi_dsi_generic_write(dsi, cmd->payload, cmd->size);
		if (ret < 0) {
			dev_err(ctx->base.dev, "init cmd %d failed: %d\n", i, ret);
			return ret;
		}

		/* Delay after sleep/exit sleep commands */
		if (cmd->payload[0] == MIPI_DCS_EXIT_SLEEP_MODE)
			msleep(120);
		else if (cmd->payload[0] == MIPI_DCS_SET_DISPLAY_ON)
			msleep(20);
		else
			usleep_range(1000, 2000);
	}

	return 0;
}

static int peridot_panel_prepare(struct drm_panel *panel)
{
	struct peridot_panel *ctx = to_peridot_panel(panel);
	int ret;

	if (ctx->prepared)
		return 0;

	ret = peridot_panel_power_on(ctx);
	if (ret)
		return ret;

	ret = peridot_panel_init_sequence(ctx);
	if (ret) {
		peridot_panel_power_off(ctx);
		return ret;
	}

	ctx->prepared = true;
	return 0;
}

static int peridot_panel_enable(struct drm_panel *panel)
{
	struct peridot_panel *ctx = to_peridot_panel(panel);

	if (ctx->enabled)
		return 0;

	/* Display on command already sent in init sequence */
	ctx->enabled = true;
	return 0;
}

static int peridot_panel_disable(struct drm_panel *panel)
{
	struct peridot_panel *ctx = to_peridot_panel(panel);

	if (!ctx->enabled)
		return 0;

	ctx->enabled = false;
	return 0;
}

static int peridot_panel_unprepare(struct drm_panel *panel)
{
	struct peridot_panel *ctx = to_peridot_panel(panel);

	if (!ctx->prepared)
		return 0;

	/* Send exit sequence */
	mipi_dsi_dcs_write_buffer(ctx->dsi, peridot_exit_cmds,
				 ARRAY_SIZE(peridot_exit_cmds));

	peridot_panel_power_off(ctx);
	ctx->prepared = false;
	return 0;
}

static int peridot_panel_get_modes(struct drm_panel *panel,
				    struct drm_connector *connector)
{
	struct peridot_panel *ctx = to_peridot_panel(panel);
	struct drm_display_mode *mode;
	struct drm_dsc_config dsc_cfg = {
		.linebuf_depth = 10,
		.bits_per_component = 10,
		.convert_rgb = true,
		.slice_count = PERIDOT_DSC_SLICE_COUNT,
		.slice_height = PERIDOT_DSC_SLICE_HEIGHT,
		.block_pred_enable = true,
		.native_420 = false,
		.native_422 = false,
		.pic_width = PERIDOT_DSC_PIC_WIDTH,
		.pic_height = PERIDOT_DSC_PIC_HEIGHT,
		.rc_model_size = 8192,
	};

	mode = drm_mode_create(connector->dev);
	if (!mode)
		return -ENOMEM;

	drm_display_mode_from_videomode(&(struct videomode){
		.hactive = PERIDOT_HACTIVE,
		.vactive = PERIDOT_VACTIVE,
		.hfront_porch = PERIDOT_HFP,
		.hsync_len = PERIDOT_HSA,
		.hback_porch = PERIDOT_HBP,
		.vfront_porch = PERIDOT_VFP,
		.vsync_len = PERIDOT_VSA,
		.vback_porch = PERIDOT_VBP,
		.pixelclock = PERIDOT_PIXCLK,
		.flags = DISPLAY_FLAGS_DE_ONLY_HIGH | DISPLAY_FLAGS_PIXDATA_POSEDGE,
	}, mode);

	mode->type = DRM_MODE_TYPE_DRIVER | DRM_MODE_TYPE_PREFERRED;
	drm_mode_set_name(mode);
	drm_mode_probed_add(connector, mode);

	/* Configure DSC */
	drm_dsc_compute_rc_parameters(&dsc_cfg);
	drm_dsc_ppts_compute(&peridot_dsc_pps, &dsc_cfg);
	connector->dsc = drm_dsc_pps_copy(&peridot_dsc_pps);

	return 1;
}

static const struct drm_panel_funcs peridot_panel_funcs = {
	.prepare = peridot_panel_prepare,
	.enable = peridot_panel_enable,
	.disable = peridot_panel_disable,
	.unprepare = peridot_panel_unprepare,
	.get_modes = peridot_panel_get_modes,
};

static int peridot_panel_probe(struct mipi_dsi_device *dsi)
{
	struct device *dev = &dsi->dev;
	struct peridot_panel *ctx;
	int ret;

	ctx = devm_kzalloc(dev, sizeof(*ctx), GFP_KERNEL);
	if (!ctx)
		return -ENOMEM;

	dsi->mode_flags = MIPI_DSI_MODE_VIDEO | MIPI_DSI_MODE_VIDEO_SYNC_PULSE |
			  MIPI_DSI_MODE_EOT_PACKET | MIPI_DSI_MODE_DSC;
	dsi->format = MIPI_DSI_FMT_RGB888;
	dsi->lanes = 4;
	dsi->hs_rate = 1500000000;  /* 1.5 Gbps per lane */
	dsi->lp_rate = 10000000;    /* 10 Mbps LP mode */

	ctx->dsi = dsi;
	mipi_dsi_set_drvdata(dsi, ctx);

	/* Reset GPIO */
	ctx->reset_gpio = devm_gpiod_get_optional(dev, "reset", GPIOD_OUT_HIGH);
	if (IS_ERR(ctx->reset_gpio)) {
		ret = PTR_ERR(ctx->reset_gpio);
		if (ret != -EPROBE_DEFER)
			dev_err(dev, "failed to get reset gpio: %d\n", ret);
		return ret;
	}

	/* Regulators: vddi (1.8V), vdda (3.3V), vdd (panel logic) */
	ctx->supplies[0].supply = "vddi";
	ctx->supplies[1].supply = "vdda";
	ctx->supplies[2].supply = "vdd";
	ret = devm_regulator_bulk_get(dev, ARRAY_SIZE(ctx->supplies), ctx->supplies);
	if (ret) {
		dev_err(dev, "failed to get regulators: %d\n", ret);
		return ret;
	}

	/* Initialize panel */
	drm_panel_init(&ctx->base, dev, &peridot_panel_funcs,
		       DRM_MODE_CONNECTOR_DSI);
	drm_panel_add(&ctx->base);

	return 0;
}

static void peridot_panel_remove(struct mipi_dsi_device *dsi)
{
	struct peridot_panel *ctx = mipi_dsi_get_drvdata(dsi);

	drm_panel_remove(&ctx->base);
}

static const struct of_device_id peridot_panel_of_match[] = {
	{ .compatible = "xiaomi,peridot-panel" },
	{ .compatible = "xiaomi,peridot-dsc-panel" },
	{},
};
MODULE_DEVICE_TABLE(of, peridot_panel_of_match);

static struct mipi_dsi_driver peridot_panel_driver = {
	.probe = peridot_panel_probe,
	.remove = peridot_panel_remove,
	.driver = {
		.name = "panel-xiaomi-peridot",
		.of_match_table = peridot_panel_of_match,
	},
};
module_mipi_dsi_driver(peridot_panel_driver);

MODULE_AUTHOR("Peridot Port <peridot@armada-dodge>");
MODULE_DESCRIPTION("Xiaomi Peridot (POCO F6) Display Panel Driver");
MODULE_LICENSE("GPL v2");