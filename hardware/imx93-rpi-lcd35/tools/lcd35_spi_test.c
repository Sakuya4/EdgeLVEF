// SPDX-License-Identifier: MIT
// Temporary, non-persistent SPI smoke test for common Waveshare/PiScreen
// 480x320 ILI9486 Raspberry Pi HAT displays on FRDM-i.MX93.

#include <errno.h>
#include <fcntl.h>
#include <linux/gpio.h>
#include <linux/spi/spidev.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <time.h>
#include <unistd.h>

#define LCD_WIDTH 480
#define LCD_HEIGHT 320

static int spi_fd = -1;
static int dc_fd = -1;

static void sleep_ms(unsigned int milliseconds)
{
    struct timespec ts = {
        .tv_sec = milliseconds / 1000,
        .tv_nsec = (long)(milliseconds % 1000) * 1000000L,
    };
    nanosleep(&ts, NULL);
}

static void die(const char *message)
{
    perror(message);
    exit(EXIT_FAILURE);
}

static void set_dc(unsigned char value)
{
    struct gpiohandle_data data = { .values = { value } };
    if (ioctl(dc_fd, GPIOHANDLE_SET_LINE_VALUES_IOCTL, &data) < 0)
        die("set LCD DC GPIO");
}

static void spi_write_all(const uint8_t *data, size_t length)
{
    while (length) {
        /* spidev's default maximum transfer buffer is commonly 4096 bytes. */
        size_t chunk = length > 4096 ? 4096 : length;
        ssize_t written = write(spi_fd, data, chunk);
        if (written < 0)
            die("SPI write");
        data += written;
        length -= (size_t)written;
    }
}

/*
 * These HATs place a serial-to-16-bit-parallel converter before the ILI9486.
 * Eight-bit commands and parameters are therefore sent as big-endian 16-bit
 * words, matching the upstream Linux DRM ili9486 driver.
 */
static void write_u8_as_u16(uint8_t value)
{
    uint8_t word[2] = { 0x00, value };
    spi_write_all(word, sizeof(word));
}

static void command(uint8_t cmd, const uint8_t *parameters, size_t count)
{
    set_dc(0);
    write_u8_as_u16(cmd);
    if (count) {
        set_dc(1);
        for (size_t i = 0; i < count; ++i)
            write_u8_as_u16(parameters[i]);
    }
}

static void init_ili9486(void)
{
    static const uint8_t pixel_format[] = { 0x55 };
    static const uint8_t power_control[] = { 0x44 };
    static const uint8_t vcom_control[] = { 0x00, 0x00, 0x00, 0x00 };
    static const uint8_t positive_gamma[] = {
        0x0f, 0x1f, 0x1c, 0x0c, 0x0f, 0x08, 0x48, 0x98,
        0x37, 0x0a, 0x13, 0x04, 0x11, 0x0d, 0x00,
    };
    static const uint8_t negative_gamma[] = {
        0x0f, 0x32, 0x2e, 0x0b, 0x0d, 0x05, 0x47, 0x75,
        0x37, 0x06, 0x10, 0x03, 0x24, 0x20, 0x00,
    };
    static const uint8_t address_mode[] = { 0xe8 }; /* landscape + BGR */

    command(0x01, NULL, 0); /* software reset */
    sleep_ms(150);
    command(0xb0, NULL, 0); /* interface control */
    command(0x11, NULL, 0); /* sleep out */
    sleep_ms(250);
    command(0x3a, pixel_format, sizeof(pixel_format));
    command(0xc2, power_control, sizeof(power_control));
    command(0xc5, vcom_control, sizeof(vcom_control));
    command(0xe0, positive_gamma, sizeof(positive_gamma));
    command(0xe1, negative_gamma, sizeof(negative_gamma));
    command(0xe2, negative_gamma, sizeof(negative_gamma));
    command(0x36, address_mode, sizeof(address_mode));
    command(0x29, NULL, 0); /* display on */
    sleep_ms(100);
}

static void set_window(void)
{
    static const uint8_t columns[] = {
        0x00, 0x00, (LCD_WIDTH - 1) >> 8, (LCD_WIDTH - 1) & 0xff,
    };
    static const uint8_t rows[] = {
        0x00, 0x00, (LCD_HEIGHT - 1) >> 8, (LCD_HEIGHT - 1) & 0xff,
    };
    command(0x2a, columns, sizeof(columns));
    command(0x2b, rows, sizeof(rows));
    command(0x2c, NULL, 0);
}

static uint16_t bar_colour(unsigned int x)
{
    static const uint16_t colours[] = {
        0xf800, /* red */
        0x07e0, /* green */
        0x001f, /* blue */
        0xffe0, /* yellow */
        0x07ff, /* cyan */
        0xf81f, /* magenta */
        0xffff, /* white */
        0x0000, /* black */
    };
    return colours[(x * (sizeof(colours) / sizeof(colours[0]))) / LCD_WIDTH];
}

static void draw_colour_bars(void)
{
    const size_t line_bytes = LCD_WIDTH * 2;
    uint8_t *line = malloc(line_bytes);
    if (!line)
        die("allocate scanline");

    for (unsigned int x = 0; x < LCD_WIDTH; ++x) {
        uint16_t colour = bar_colour(x);
        line[x * 2] = (uint8_t)(colour >> 8);
        line[x * 2 + 1] = (uint8_t)colour;
    }

    set_window();
    set_dc(1);
    for (unsigned int y = 0; y < LCD_HEIGHT; ++y)
        spi_write_all(line, line_bytes);
    free(line);
}

static int request_gpio_line(const char *chip_path, unsigned int offset)
{
    int chip_fd = open(chip_path, O_RDONLY | O_CLOEXEC);
    if (chip_fd < 0)
        die("open GPIO chip");

    struct gpiohandle_request request = {
        .lineoffsets = { offset },
        .flags = GPIOHANDLE_REQUEST_OUTPUT,
        .default_values = { 0 },
        .lines = 1,
    };
    snprintf(request.consumer_label, sizeof(request.consumer_label),
             "lcd35-spi-test");
    if (ioctl(chip_fd, GPIO_GET_LINEHANDLE_IOCTL, &request) < 0)
        die("request LCD DC GPIO");
    close(chip_fd);
    return request.fd;
}

int main(int argc, char **argv)
{
    const char *spi_path = argc > 1 ? argv[1] : "/dev/spidev0.0";
    const char *gpiochip_path = argc > 2 ? argv[2] : "/dev/gpiochip0";
    unsigned int dc_offset = argc > 3 ? (unsigned int)strtoul(argv[3], NULL, 0) : 24;
    uint8_t mode = SPI_MODE_0;
    uint8_t bits = 8;
    uint32_t speed = 16000000;

    dc_fd = request_gpio_line(gpiochip_path, dc_offset);
    spi_fd = open(spi_path, O_WRONLY | O_CLOEXEC);
    if (spi_fd < 0)
        die("open SPI device");
    if (ioctl(spi_fd, SPI_IOC_WR_MODE, &mode) < 0 ||
        ioctl(spi_fd, SPI_IOC_WR_BITS_PER_WORD, &bits) < 0 ||
        ioctl(spi_fd, SPI_IOC_WR_MAX_SPEED_HZ, &speed) < 0)
        die("configure SPI device");

    fprintf(stderr,
            "Testing ILI9486 on %s, DC=%s line %u, speed=%u Hz\n",
            spi_path, gpiochip_path, dc_offset, speed);
    init_ili9486();
    draw_colour_bars();
    fprintf(stderr, "Colour-bar frame sent successfully.\n");

    close(spi_fd);
    close(dc_fd);
    return 0;
}
