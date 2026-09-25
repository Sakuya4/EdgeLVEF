// SPDX-License-Identifier: MIT
// Temporary userspace XPT2046 wiring test for FRDM-i.MX93 P11.

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

static void die(const char *message)
{
    perror(message);
    exit(EXIT_FAILURE);
}

static int request_line(int chip_fd, unsigned int offset, int output,
                        unsigned char initial, const char *label)
{
    struct gpiohandle_request request = {
        .lineoffsets = { offset },
        .flags = output ? GPIOHANDLE_REQUEST_OUTPUT : GPIOHANDLE_REQUEST_INPUT,
        .default_values = { initial },
        .lines = 1,
    };
    snprintf(request.consumer_label, sizeof(request.consumer_label), "%s", label);
    if (ioctl(chip_fd, GPIO_GET_LINEHANDLE_IOCTL, &request) < 0)
        die("request GPIO line");
    return request.fd;
}

static void set_line(int fd, unsigned char value)
{
    struct gpiohandle_data data = { .values = { value } };
    if (ioctl(fd, GPIOHANDLE_SET_LINE_VALUES_IOCTL, &data) < 0)
        die("set GPIO line");
}

static unsigned char get_line(int fd)
{
    struct gpiohandle_data data = { 0 };
    if (ioctl(fd, GPIOHANDLE_GET_LINE_VALUES_IOCTL, &data) < 0)
        die("get GPIO line");
    return data.values[0];
}

static uint16_t read_channel(int spi_fd, int cs_fd, uint8_t command)
{
    uint8_t tx[3] = { command, 0, 0 };
    uint8_t rx[3] = { 0 };
    struct spi_ioc_transfer transfer = {
        .tx_buf = (uintptr_t)tx,
        .rx_buf = (uintptr_t)rx,
        .len = sizeof(tx),
        .speed_hz = 2000000,
        .bits_per_word = 8,
    };

    set_line(cs_fd, 0);
    if (ioctl(spi_fd, SPI_IOC_MESSAGE(1), &transfer) < 0) {
        set_line(cs_fd, 1);
        die("XPT2046 SPI transfer");
    }
    set_line(cs_fd, 1);
    return (uint16_t)((((uint16_t)rx[1] << 8) | rx[2]) >> 3) & 0x0fff;
}

int main(void)
{
    int gpiochip_fd = open("/dev/gpiochip0", O_RDONLY | O_CLOEXEC);
    if (gpiochip_fd < 0)
        die("open /dev/gpiochip0");
    int cs_fd = request_line(gpiochip_fd, 7, 1, 1, "xpt2046-test-cs");
    int irq_fd = request_line(gpiochip_fd, 17, 0, 0, "xpt2046-test-irq");

    int spi_fd = open("/dev/spidev0.0", O_RDWR | O_CLOEXEC);
    if (spi_fd < 0)
        die("open /dev/spidev0.0");
    /*
     * i.MX LPSPI rejects SPI_NO_CS. During this temporary wiring test its
     * native CS0 may also pulse while GPIO CS1 selects the touch controller.
     * The display is reinitialized after the test.
     */
    uint8_t mode = SPI_MODE_0;
    uint8_t bits = 8;
    uint32_t speed = 2000000;
    if (ioctl(spi_fd, SPI_IOC_WR_MODE, &mode) < 0 ||
        ioctl(spi_fd, SPI_IOC_WR_BITS_PER_WORD, &bits) < 0 ||
        ioctl(spi_fd, SPI_IOC_WR_MAX_SPEED_HZ, &speed) < 0)
        die("configure XPT2046 SPI");

    puts("Touch the panel now (20-second direct-read test)...");
    fflush(stdout);
    int samples = 0;
    for (int i = 0; i < 100; ++i) {
        uint16_t x = read_channel(spi_fd, cs_fd, 0xd0);
        uint16_t y = read_channel(spi_fd, cs_fd, 0x90);
        uint16_t z1 = read_channel(spi_fd, cs_fd, 0xb0);
        uint16_t z2 = read_channel(spi_fd, cs_fd, 0xc0);
        unsigned char irq = get_line(irq_fd);
        printf("irq=%u raw: x=%4u y=%4u z1=%4u z2=%4u\n",
               irq, x, y, z1, z2);
        fflush(stdout);
        if (!irq || z1 > 50)
            ++samples;
        usleep(200000);
    }
    printf("Touch samples captured: %d\n", samples);

    close(spi_fd);
    close(irq_fd);
    close(cs_fd);
    close(gpiochip_fd);
    return samples ? EXIT_SUCCESS : 2;
}
