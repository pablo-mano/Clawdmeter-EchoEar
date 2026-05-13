#include "power.h"
#include "display_cfg.h"
#include <Arduino.h>
#include <Wire.h>

#define BATTERY_POLL_MS   5000
#define CHARGING_POLL_MS  2000

// BQ27220 standard registers (LE 16-bit)
#define BQ27220_REG_FLAGS  0x06   // bit 0: DSG (1=discharging, 0=charging/full)
#define BQ27220_REG_SOC    0x1C   // State Of Charge, 0-100

static bool     bq_ok            = false;
static int      cached_pct       = -1;
static bool     cached_charging  = false;
static bool     pwr_pressed_flag = false;
static uint32_t last_battery_ms  = 0;
static uint32_t last_charging_ms = 0;

static uint16_t bq_read16(uint8_t reg) {
    Wire.beginTransmission(BQ27220_ADDR);
    Wire.write(reg);
    if (Wire.endTransmission(false) != 0) return 0xFFFF;
    Wire.requestFrom((uint8_t)BQ27220_ADDR, (uint8_t)2);
    if (Wire.available() < 2) return 0xFFFF;
    uint16_t lo = Wire.read();
    uint16_t hi = Wire.read();
    return (hi << 8) | lo;
}

void power_init(void) {
    Wire.beginTransmission(BQ27220_ADDR);
    bq_ok = (Wire.endTransmission() == 0);
    if (!bq_ok) {
        Serial.println("BQ27220 not found");
        return;
    }
    Serial.println("BQ27220 init OK");

    uint16_t soc   = bq_read16(BQ27220_REG_SOC);
    uint16_t flags = bq_read16(BQ27220_REG_FLAGS);
    if (soc   <= 100)   cached_pct      = (int)soc;
    if (flags != 0xFFFF) cached_charging = !(flags & 0x0001);
}

void power_tick(void) {
    if (!bq_ok) return;
    uint32_t now = millis();

    if (now - last_charging_ms >= CHARGING_POLL_MS) {
        last_charging_ms = now;
        uint16_t flags = bq_read16(BQ27220_REG_FLAGS);
        if (flags != 0xFFFF) cached_charging = !(flags & 0x0001);
    }
    if (now - last_battery_ms >= BATTERY_POLL_MS) {
        last_battery_ms = now;
        uint16_t soc = bq_read16(BQ27220_REG_SOC);
        if (soc <= 100) cached_pct = (int)soc;
    }
}

int  power_battery_pct(void)  { return cached_pct; }
bool power_is_charging(void)  { return cached_charging; }

bool power_pwr_pressed(void) {
    if (pwr_pressed_flag) {
        pwr_pressed_flag = false;
        return true;
    }
    return false;
}

void power_set_pwr_pressed(void) {
    pwr_pressed_flag = true;
}
