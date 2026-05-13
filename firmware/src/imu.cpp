#include "imu.h"
#include "display_cfg.h"
#include <Arduino.h>

// BMI270 is not yet supported by SensorLib 0.2.6.
// Stub implementation: rotation fixed at 0 (portrait).
// TODO: add BMI270 library when available and restore full rotation logic.

void imu_init(void) {
    Serial.println("IMU: BMI270 stub (auto-rotation disabled)");
}

void imu_tick(void) {
    // no-op
}

uint8_t imu_get_rotation(void) {
    return 0;
}
