#pragma once

void power_init(void);
void power_tick(void);
int  power_battery_pct(void);       // 0-100, or -1 if unavailable
bool power_is_charging(void);
bool power_pwr_pressed(void);       // true once per BTN_PWR edge (GPIO7)
void power_set_pwr_pressed(void);   // called from main loop on GPIO7 falling edge
