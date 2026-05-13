#pragma once

#include <Arduino_GFX_Library.h>
#include <TouchDrvCSTXXX.hpp>
#include <Wire.h>

// ---- Display resolution ----
#define LCD_WIDTH   360
#define LCD_HEIGHT  360

// ---- QSPI display pins (ST77916, ESP-VoCat v1.2) ----
// GPIO45 (DC/DCX) is wired on the PCB but not passed to Arduino_GFX:
// QSPI command/data mode is encoded in the 32-bit opcode framing.
// GPIO45 is also an ESP32-S3 strapping pin — PCB pulls it correctly at boot.
#define LCD_CS      14
#define LCD_SCLK    18
#define LCD_SDIO0   46
#define LCD_SDIO1   13
#define LCD_SDIO2   11
#define LCD_SDIO3   12
#define LCD_RESET   47
#define LCD_BL      44   // backlight PWM (5 kHz via analogWrite)

// ---- Touch (CST816S via shared I2C) ----
#define IIC_SDA      2
#define IIC_SCL      1
#define TP_INT       10
#define TP_RST       -1   // RST is NC on ESP-VoCat v1.2
#define CST816S_ADDR 0x15

// ---- IMU (BMI270 via shared I2C) ----
#define BMI270_ADDR  0x68

// ---- Fuel gauge (BQ27220 via shared I2C) ----
#define BQ27220_ADDR 0x55

// ---- Global hardware objects (defined in main.cpp) ----
extern Arduino_DataBus  *bus;
extern Arduino_ST77916  *gfx;
extern TouchDrvCSTXXX    touch;
