/* 138 preparation: bounded READ-only USB -> native RS485. No motion opcodes.
 * Default app_main returns without explicit UART/USB initialization or TX.
 * This says nothing about ROM/bootloader output or existing factory firmware.
 */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "driver/uart.h"
#include "driver/usb_serial_jtag.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#ifndef WRIST138_HARDWARE_PERMIT
#define WRIST138_HARDWARE_PERMIT 0
#endif

#define BUS UART_NUM_1
#define LINE_CAP 24
#define LINE_TIMEOUT_US 500000
#define REPLY_TIMEOUT_US 200000

static unsigned sum8(const uint8_t *p, size_t n) {
    unsigned s = 0;
    for (size_t i = 0; i < n; ++i) s += p[i];
    return s & 255u;
}

static size_t reply_size(unsigned code) {
    switch (code) {
        case 0x31: return 10;
        case 0x32: return 6;
        case 0xF1: case 0x3A: return 5;
        default: return 0;
    }
}

static int hex_nibble(unsigned char c) {
    if (c >= '0' && c <= '9') return (int)(c - '0');
    if (c >= 'A' && c <= 'F') return (int)(c - 'A') + 10;
    if (c >= 'a' && c <= 'f') return (int)(c - 'a') + 10;
    return -1;
}

static bool parse_read(const char *line, size_t n, unsigned *node, unsigned *code) {
    if (n && line[n - 1] == '\r') --n; /* CRLF is accepted, embedded CR is not. */
    if (n < 9 || n >= LINE_CAP || memcmp(line, "READ ", 5) != 0) return false;
    size_t i = 5, digits = 0;
    unsigned addr = 0;
    while (i < n && line[i] >= '0' && line[i] <= '9') {
        if (++digits > 3) return false;
        addr = addr * 10u + (unsigned)(line[i++] - '0');
    }
    if (!digits || addr == 0 || addr > 255 || i + 3 != n || line[i++] != ' ') return false;
    int h = hex_nibble((unsigned char)line[i]), l = hex_nibble((unsigned char)line[i + 1]);
    if (h < 0 || l < 0) return false;
    unsigned op = (unsigned)(h * 16 + l);
    if (!reply_size(op)) return false;
    *node = addr; *code = op;
    return true;
}

static bool valid_reply(const uint8_t *p, size_t n, unsigned node, unsigned code) {
    if (!reply_size(code) || n != reply_size(code) || p[0] != 0xFB ||
        p[1] != node || p[2] != code || sum8(p, n - 1) != p[n - 1]) return false;
    if (code == 0x3A && p[3] > 1) return false;
    if (code == 0xF1 && (p[3] < 1 || p[3] > 6)) return false;
    return true;
}

static void report_text(const char *s) {
    /* Debug evidence only; no use of the hardware UART from printf. */
    (void)usb_serial_jtag_write_bytes(s, strlen(s), pdMS_TO_TICKS(20));
}

static bool serve_line(const char *line, size_t n) {
    unsigned node = 0, code = 0;
    if (!parse_read(line, n, &node, &code)) {
        report_text("ERROR invalid READ request\n");
        return false;
    }
    uint8_t tx[4] = {0xFA, (uint8_t)node, (uint8_t)code, 0};
    tx[3] = (uint8_t)sum8(tx, 3);
    if (uart_flush_input(BUS) != ESP_OK || uart_write_bytes(BUS, tx, sizeof tx) != (int)sizeof tx ||
        uart_wait_tx_done(BUS, pdMS_TO_TICKS(100)) != ESP_OK) {
        report_text("ERROR UART TX incomplete; no retry\n");
        return false;
    }
    uint8_t rx[11];
    size_t used = 0, expected = reply_size(code);
    const int64_t start = esp_timer_get_time();
    for (;;) {
        int64_t now = esp_timer_get_time();
        if (now < start) { report_text("ERROR clock reversed\n"); return false; }
        if (now - start >= REPLY_TIMEOUT_US) break;
        unsigned ms = (unsigned)((REPLY_TIMEOUT_US - (now - start) + 999) / 1000);
        int got = uart_read_bytes(BUS, rx + used, expected + 1 - used, pdMS_TO_TICKS(ms));
        if (got < 0 || (size_t)got > expected + 1 - used) {
            report_text("ERROR UART RX\n"); return false;
        }
        used += (size_t)got;
        if (used > expected) { report_text("ERROR trailing UART data\n"); return false; }
        if (got == 0) break; /* bounded SDK timeout, not a partial-frame success */
    }
    if (!valid_reply(rx, used, node, code)) {
        report_text("ERROR timeout/partial/mismatched reply\n");
        return false;
    }
    char response[96];
    int offset = snprintf(response, sizeof response, "READ_REPLY %u %02X ", node, code);
    for (size_t i = 0; i < used && offset > 0 && (size_t)offset < sizeof response - 4; ++i)
        offset += snprintf(response + offset, sizeof response - (size_t)offset, "%02X%s", rx[i], i + 1 == used ? "\n" : " ");
    if (offset <= 0 || (size_t)offset >= sizeof response) return false;
    report_text(response);
    return true;
}

typedef struct {
    char text[LINE_CAP];
    size_t used;
    bool dropping;
    int64_t first_us;
} LineState;

static void expire_line(LineState *s, int64_t now) {
    if ((s->used || s->dropping) && (now < s->first_us || now - s->first_us >= LINE_TIMEOUT_US)) {
        if (!s->dropping) report_text("ERROR partial USB line timed out; discard through newline\n");
        s->used = 0; s->dropping = true;
    }
}

static void feed_byte(LineState *s, uint8_t byte, int64_t now) {
    expire_line(s, now);
    if (byte == '\n') {
        if (!s->dropping && s->used) (void)serve_line(s->text, s->used);
        s->used = 0; s->dropping = false; s->first_us = 0;
        return;
    }
    if (s->dropping) return;
    if (!s->used) s->first_us = now;
    if ((byte < 0x20 && byte != '\r') || byte > 0x7E || s->used >= LINE_CAP - 1) {
        report_text("ERROR invalid/oversized USB line; discard through newline\n");
        s->used = 0; s->dropping = true;
        return;
    }
    s->text[s->used++] = (char)byte;
}

static void bridge_run(void) {
    const uart_config_t config = {.baud_rate = 38400, .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE, .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE, .source_clk = UART_SCLK_DEFAULT};
    const usb_serial_jtag_driver_config_t usb = {.tx_buffer_size = 512, .rx_buffer_size = 512};
    if (usb_serial_jtag_driver_install(&usb) != ESP_OK) return;
    if (uart_driver_install(BUS, 256, 0, 0, NULL, 0) != ESP_OK) {
        report_text("ERROR UART install\n"); usb_serial_jtag_driver_uninstall(); return;
    }
    if (uart_param_config(BUS, &config) != ESP_OK ||
        uart_set_pin(BUS, 17, 18, 21, UART_PIN_NO_CHANGE) != ESP_OK ||
        uart_set_mode(BUS, UART_MODE_RS485_HALF_DUPLEX) != ESP_OK) {
        report_text("ERROR UART setup\n"); uart_driver_delete(BUS); usb_serial_jtag_driver_uninstall(); return;
    }
    LineState line = {0};
    report_text("READY READ_ONLY 38400_8N1 candidate; hardware settings must match\n");
    for (;;) {
        uint8_t byte;
        int n = usb_serial_jtag_read_bytes(&byte, 1, pdMS_TO_TICKS(20));
        int64_t now = esp_timer_get_time();
        if (n < 0 || n > 1) { report_text("ERROR USB closed; no retry\n"); break; }
        if (n == 0) expire_line(&line, now);
        else feed_byte(&line, byte, now);
    }
    uart_driver_delete(BUS);
    usb_serial_jtag_driver_uninstall();
}

void app_main(void) {
    if (WRIST138_HARDWARE_PERMIT != 1) return;
    bridge_run();
}
