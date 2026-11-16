/*
 * Goodix GT9916R (Berlin-D) Touchscreen Driver for Xiaomi Peridot
 *
 * Interface: SPI via QUPv3 SE4
 * GPIOs: MISO=16, MOSI=17, CLK=18, CS=19, INT=129, RESET=128
 * Power: LDOB23 (1.8V) + LDOB13 (3.3V) via RPMh
 *
 * Adapted from:
 * - armada-dodge op13-touch.c (S3910 SPI bitbang)
 * - xnu-kernel-peridot hakios.goodix.c (Goodix GT9916R on SPI)
 * - Linux kernel goodix driver
 */

#include <linux/delay.h>
#include <linux/gpio/consumer.h>
#include <linux/interrupt.h>
#include <linux/input/mt.h>
#include <linux/module.h>
#include <linux/of_device.h>
#include <linux/regulator/consumer.h>
#include <linux/spi/spi.h>
#include <linux/firmware.h>

/* Goodix GT9916R Registers */
#define GOODIX_REG_ID			0x0000
#define GOODIX_REG_CONFIG_VERSION	0x0001
#define GOODIX_REG_FW_VERSION		0x0002
#define GOODIX_REG_VENDOR_ID		0x0004
#define GOODIX_REG_IC_INFO		0x0008
#define GOODIX_REG_TOUCH_DATA		0x10000  /* Touch report starts here */

/* IC Info structure (at 0x0008) */
#define GOODIX_IC_INFO_SIZE		64
#define GOODIX_MAX_TOUCH		10
#define GOODIX_TOUCH_DATA_SIZE		8  /* Per touch point */

/* Touch report format (from Goodix spec) */
#define GOODIX_TOUCH_STATUS		0x00  /* Bit 0: touch, Bit 7: large area */
#define GOODIX_TOUCH_X_LOW		0x01
#define GOODIX_TOUCH_X_HIGH		0x02
#define GOODIX_TOUCH_Y_LOW		0x03
#define GOODIX_TOUCH_Y_HIGH		0x04
#define GOODIX_TOUCH_WIDTH		0x05
#define GOODIX_TOUCH_PRESSURE		0x06

/* Commands */
#define GOODIX_CMD_RESET		0x00
#define GOODIX_CMD_READ_COOR		0x80
#define GOODIX_CMD_GESTURE		0xD0

/* Configuration */
#define GOODIX_CONFIG_LENGTH		186
#define GOODIX_FW_NAME		"goodix_gt9916r_peridot.fw"
#define GOODIX_CFG_NAME		"goodix_gt9916r_peridot.cfg"

/* Peridot-specific coordinates (from xnu-kernel-peridot) */
#define PERIDOT_TOUCH_MAX_X		19520
#define PERIDOT_TOUCH_MAX_Y		43400

struct goodix_ts_data {
	struct spi_device *spi;
	struct input_dev *input_dev;
	struct gpio_desc *reset_gpio;
	struct gpio_desc *int_gpio;
	struct regulator *vdd_1v8;
	struct regulator *vdd_3v3;
	struct mutex lock;
	struct completion firmware_loaded;
	bool suspended;
	bool gesture_enabled;
	u8 *config_data;
	size_t config_len;
	u16 max_x;
	u16 max_y;
	u8 touch_points;
	u8 int_trigger_type;
	struct delayed_work work;
};

/* SPI read/write helpers */
static int goodix_spi_read(struct goodix_ts_data *ts, u16 reg, u8 *buf, int len)
{
	struct spi_message msg;
	struct spi_transfer xfer[2] = {};
	u8 tx_buf[2] = { reg >> 8, reg & 0xFF };
	int ret;

	spi_message_init(&msg);

	xfer[0].tx_buf = tx_buf;
	xfer[0].len = 2;
	spi_message_add_tail(&xfer[0], &msg);

	xfer[1].rx_buf = buf;
	xfer[1].len = len;
	spi_message_add_tail(&xfer[1], &msg);

	ret = spi_sync(ts->spi, &msg);
	return ret;
}

static int goodix_spi_write(struct goodix_ts_data *ts, u16 reg, const u8 *buf, int len)
{
	struct spi_message msg;
	struct spi_transfer xfer[2] = {};
	u8 *tx_buf;
	int ret;

	tx_buf = kmalloc(2 + len, GFP_KERNEL);
	if (!tx_buf)
		return -ENOMEM;

	tx_buf[0] = reg >> 8;
	tx_buf[1] = reg & 0xFF;
	memcpy(tx_buf + 2, buf, len);

	spi_message_init(&msg);

	xfer[0].tx_buf = tx_buf;
	xfer[0].len = 2 + len;
	spi_message_add_tail(&xfer[0], &msg);

	ret = spi_sync(ts->spi, &msg);
	kfree(tx_buf);
	return ret;
}

/* Read touch points */
static int goodix_read_touch_data(struct goodix_ts_data *ts)
{
	u8 buf[GOODIX_TOUCH_DATA_SIZE * GOODIX_MAX_TOUCH + 1];
	int ret, i, touch_num;

	ret = goodix_spi_read(ts, GOODIX_REG_TOUCH_DATA, buf, sizeof(buf));
	if (ret < 0)
		return ret;

	touch_num = buf[0] & 0x0F;
	if (touch_num > GOODIX_MAX_TOUCH || touch_num == 0)
		return 0;

	for (i = 0; i < touch_num; i++) {
		u8 *point = &buf[1 + i * GOODIX_TOUCH_DATA_SIZE];
		u16 x = point[GOODIX_TOUCH_X_LOW] | (point[GOODIX_TOUCH_X_HIGH] << 8);
		u16 y = point[GOODIX_TOUCH_Y_LOW] | (point[GOODIX_TOUCH_Y_HIGH] << 8);
		u16 w = point[GOODIX_TOUCH_WIDTH];
		u8 pressure = point[GOODIX_TOUCH_PRESSURE];
		bool touch = point[GOODIX_TOUCH_STATUS] & 0x01;

		if (!touch)
			continue;

		/* Clamp to screen resolution */
		if (x > ts->max_x) x = ts->max_x;
		if (y > ts->max_y) y = ts->max_y;

		input_mt_slot(ts->input_dev, i);
		input_mt_report_slot_state(ts->input_dev, MT_TOOL_FINGER, touch);
		if (touch) {
			input_report_abs(ts->input_dev, ABS_MT_POSITION_X, x);
			input_report_abs(ts->input_dev, ABS_MT_POSITION_Y, y);
			input_report_abs(ts->input_dev, ABS_MT_TOUCH_MAJOR, w);
			input_report_abs(ts->input_dev, ABS_MT_PRESSURE, pressure);
		}
	}

	/* Report empty slots */
	for (; i < ts->touch_points; i++) {
		input_mt_slot(ts->input_dev, i);
		input_mt_report_slot_state(ts->input_dev, MT_TOOL_FINGER, false);
	}

	input_mt_report_pointer_emulation(ts->input_dev, true);
	input_sync(ts->input_dev);

	return touch_num;
}

/* Interrupt handler */
static irqreturn_t goodix_irq_handler(int irq, void *dev_id)
{
	struct goodix_ts_data *ts = dev_id;

	if (ts->suspended) {
		/* Handle gesture wakeup */
		if (ts->gesture_enabled) {
			// TODO: Read gesture data
		}
		return IRQ_HANDLED;
	}

	queue_delayed_work(system_wq, &ts->work, 0);
	return IRQ_HANDLED;
}

static void goodix_work_func(struct work_struct *work)
{
	struct goodix_ts_data *ts = container_of(work, struct goodix_ts_data, work.work);

	mutex_lock(&ts->lock);
	goodix_read_touch_data(ts);
	mutex_unlock(&ts->lock);
}

/* Firmware loading */
static int goodix_load_firmware(struct goodix_ts_data *ts)
{
	const struct firmware *fw;
	int ret;

	ret = request_firmware(&fw, GOODIX_FW_NAME, &ts->spi->dev);
	if (ret) {
		dev_warn(&ts->spi->dev, "firmware %s not found: %d\n", GOODIX_FW_NAME, ret);
		return ret;
	}

	/* Write firmware to device (implementation depends on Goodix protocol) */
	/* This is a simplified version - actual Goodix firmware update is more complex */
	dev_info(&ts->spi->dev, "firmware loaded, size: %zu\n", fw->size);

	release_firmware(fw);
	complete(&ts->firmware_loaded);
	return 0;
}

static int goodix_load_config(struct goodix_ts_data *ts)
{
	const struct firmware *fw;
	int ret;

	ret = request_firmware(&fw, GOODIX_CFG_NAME, &ts->spi->dev);
	if (ret) {
		dev_warn(&ts->spi->dev, "config %s not found: %d\n", GOODIX_CFG_NAME, ret);
		return ret;
	}

	ts->config_data = kmemdup(fw->data, fw->size, GFP_KERNEL);
	if (!ts->config_data) {
		ret = -ENOMEM;
		goto out;
	}

	ts->config_len = fw->size;
	dev_info(&ts->spi->dev, "config loaded, size: %zu\n", fw->size);

	/* Write config to device */
	ret = goodix_spi_write(ts, GOODIX_REG_CONFIG_VERSION, ts->config_data, ts->config_len);
	if (ret)
		dev_err(&ts->spi->dev, "config write failed: %d\n", ret);

out:
	release_firmware(fw);
	return ret;
}

/* Chip identification */
static int goodix_identify(struct goodix_ts_data *ts)
{
	u8 buf[4];
	int ret;

	ret = goodix_spi_read(ts, GOODIX_REG_ID, buf, 4);
	if (ret < 0)
		return ret;

	dev_info(&ts->spi->dev, "ID: %02X%02X%02X%02X\n", buf[0], buf[1], buf[2], buf[3]);

	/* Check for GT9916R (Berlin-D) */
	if (buf[0] == 0x99 && buf[1] == 0x16) {
		dev_info(&ts->spi->dev, "Goodix GT9916R detected\n");
		return 0;
	}

	return -ENODEV;
}

/* Reset sequence */
static int goodix_hw_reset(struct goodix_ts_data *ts)
{
	if (!ts->reset_gpio)
		return 0;

	gpiod_set_value_cansleep(ts->reset_gpio, 0);
	msleep(10);
	gpiod_set_value_cansleep(ts->reset_gpio, 1);
	msleep(50);  /* Goodix needs ~50ms after reset */

	return 0;
}

/* Power management */
static int goodix_power_on(struct goodix_ts_data *ts)
{
	int ret;

	ret = regulator_enable(ts->vdd_1v8);
	if (ret) {
		dev_err(&ts->spi->dev, "failed to enable vdd_1v8: %d\n", ret);
		return ret;
	}

	ret = regulator_enable(ts->vdd_3v3);
	if (ret) {
		dev_err(&ts->spi->dev, "failed to enable vdd_3v3: %d\n", ret);
		regulator_disable(ts->vdd_1v8);
		return ret;
	}

	msleep(5);  /* Power stabilization */

	return goodix_hw_reset(ts);
}

static int goodix_power_off(struct goodix_ts_data *ts)
{
	regulator_disable(ts->vdd_3v3);
	regulator_disable(ts->vdd_1v8);
	return 0;
}

/* Probe */
static int goodix_ts_probe(struct spi_device *spi)
{
	struct device *dev = &spi->dev;
	struct goodix_ts_data *ts;
	int ret;

	ts = devm_kzalloc(dev, sizeof(*ts), GFP_KERNEL);
	if (!ts)
		return -ENOMEM;

	spi_set_drvdata(spi, ts);
	ts->spi = spi;

	/* SPI setup */
	spi->mode = SPI_MODE_0;
	spi->bits_per_word = 8;
	spi->max_speed_hz = 4000000;  /* 4 MHz */
	ret = spi_setup(spi);
	if (ret) {
		dev_err(dev, "spi_setup failed: %d\n", ret);
		return ret;
	}

	/* GPIOs */
	ts->reset_gpio = devm_gpiod_get_optional(dev, "reset", GPIOD_OUT_HIGH);
	if (IS_ERR(ts->reset_gpio)) {
		ret = PTR_ERR(ts->reset_gpio);
		if (ret != -EPROBE_DEFER)
			dev_err(dev, "failed to get reset gpio: %d\n", ret);
		return ret;
	}

	ts->int_gpio = devm_gpiod_get_optional(dev, "interrupt", GPIOD_IN);
	if (IS_ERR(ts->int_gpio)) {
		ret = PTR_ERR(ts->int_gpio);
		if (ret != -EPROBE_DEFER)
			dev_err(dev, "failed to get int gpio: %d\n", ret);
		return ret;
	}

	/* Regulators */
	ts->vdd_1v8 = devm_regulator_get(dev, "vdd_1v8");
	if (IS_ERR(ts->vdd_1v8)) {
		ret = PTR_ERR(ts->vdd_1v8);
		dev_err(dev, "failed to get vdd_1v8: %d\n", ret);
		return ret;
	}

	ts->vdd_3v3 = devm_regulator_get(dev, "vdd_3v3");
	if (IS_ERR(ts->vdd_3v3)) {
		ret = PTR_ERR(ts->vdd_3v3);
		dev_err(dev, "failed to get vdd_3v3: %d\n", ret);
		return ret;
	}

	/* Power on */
	ret = goodix_power_on(ts);
	if (ret)
		return ret;

	/* Identify chip */
	ret = goodix_identify(ts);
	if (ret) {
		goodix_power_off(ts);
		return ret;
	}

	/* Load firmware and config */
	init_completion(&ts->firmware_loaded);
	goodix_load_firmware(ts);
	goodix_load_config(ts);

	/* Wait for firmware load */
	wait_for_completion_timeout(&ts->firmware_loaded, msecs_to_jiffies(2000));

	/* Input device */
	ts->input_dev = devm_input_allocate_device(dev);
	if (!ts->input_dev)
		return -ENOMEM;

	ts->input_dev->name = "Goodix GT9916R Touchscreen";
	ts->input_dev->id.bustype = BUS_SPI;
	ts->input_dev->dev.parent = dev;

	/* Touch capabilities */
	ts->max_x = PERIDOT_TOUCH_MAX_X;
	ts->max_y = PERIDOT_TOUCH_MAX_Y;
	ts->touch_points = GOODIX_MAX_TOUCH;

	input_set_abs_params(ts->input_dev, ABS_MT_POSITION_X, 0, ts->max_x, 0, 0);
	input_set_abs_params(ts->input_dev, ABS_MT_POSITION_Y, 0, ts->max_y, 0, 0);
	input_set_abs_params(ts->input_dev, ABS_MT_TOUCH_MAJOR, 0, 255, 0, 0);
	input_set_abs_params(ts->input_dev, ABS_MT_PRESSURE, 0, 255, 0, 0);
	input_mt_init_slots(ts->input_dev, ts->touch_points, INPUT_MT_DIRECT);

	/* Interrupt */
	if (ts->int_gpio) {
		int irq = gpiod_to_irq(ts->int_gpio);
		if (irq > 0) {
			ts->int_trigger_type = IRQF_TRIGGER_FALLING | IRQF_ONESHOT;
			ret = devm_request_threaded_irq(dev, irq, NULL, goodix_irq_handler,
							ts->int_trigger_type, "goodix-touch", ts);
			if (ret) {
				dev_err(dev, "failed to request irq: %d\n", ret);
				return ret;
			}
		}
	}

	/* Work queue for touch reading */
	INIT_DELAYED_WORK(&ts->work, goodix_work_func);
	mutex_init(&ts->lock);

	ret = input_register_device(ts->input_dev);
	if (ret)
		return ret;

	dev_info(dev, "Goodix GT9916R touchscreen registered\n");
	return 0;
}

static void goodix_ts_remove(struct spi_device *spi)
{
	struct goodix_ts_data *ts = spi_get_drvdata(spi);

	cancel_delayed_work_sync(&ts->work);
	input_unregister_device(ts->input_dev);
	goodix_power_off(ts);
	kfree(ts->config_data);
}

static int goodix_ts_suspend(struct device *dev)
{
	struct goodix_ts_data *ts = dev_get_drvdata(dev);

	ts->suspended = true;
	disable_irq(gpiod_to_irq(ts->int_gpio));
	return 0;
}

static int goodix_ts_resume(struct device *dev)
{
	struct goodix_ts_data *ts = dev_get_drvdata(dev);

	enable_irq(gpiod_to_irq(ts->int_gpio));
	goodix_hw_reset(ts);
	ts->suspended = false;
	return 0;
}

static const struct dev_pm_ops goodix_pm_ops = {
	.suspend = goodix_ts_suspend,
	.resume = goodix_ts_resume,
};

static const struct of_device_id goodix_ts_of_match[] = {
	{ .compatible = "goodix,gt9916r" },
	{ .compatible = "xiaomi,peridot-touch" },
	{},
};
MODULE_DEVICE_TABLE(of, goodix_ts_of_match);

static struct spi_driver goodix_ts_driver = {
	.driver = {
		.name = "goodix-gt9916r",
		.of_match_table = goodix_ts_of_match,
		.pm = &goodix_pm_ops,
	},
	.probe = goodix_ts_probe,
	.remove = goodix_ts_remove,
};
module_spi_driver(goodix_ts_driver);

MODULE_AUTHOR("Peridot Port <peridot@armada-dodge>");
MODULE_DESCRIPTION("Goodix GT9916R Touchscreen Driver for Xiaomi Peridot");
MODULE_LICENSE("GPL v2");
MODULE_FIRMWARE(GOODIX_FW_NAME);
MODULE_FIRMWARE(GOODIX_CFG_NAME);