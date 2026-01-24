# Radxa ROCK 5 ITX Intelligent Fan Control

This project provides a custom, intelligent fan control solution for the **Radxa ROCK 5 ITX** (RK3588). It replaces the default "always-on" behavior with a temperature-based curve, real-time RPM monitoring, and a startup self-test.

## 🌟 Features
*   **Intelligent Thermal Curve**: Automatically adjusts fan speed based on CPU temperature.
*   **Live RPM Monitoring**: Uses GPIO interrupts to read and log fan tachometer data.
*   **Startup Self-Test**: Cycles through all fan speeds on startup to verify hardware health.
*   **Systemd Integration**: Runs as a background service with unbuffered logging.
*   **No Overlay Required**: Directly targets hardware addresses to ensure stability across kernel updates.

## 🛠️ Technical Insights (Why this works)
During development, we discovered that:
1.  **PWM Address**: While schematics refer to PWM14, the accessible register on the ROCK 5 ITX for the fan header is at `febf0020`.
2.  **Driver Conflict**: The kernel's generic `pwm-fan` driver often claims this resource first but provides limited control. This script automatically unbinds the generic driver to allow direct PWM access.
3.  **Tachometer Mapping**: The `FAN_SPEED` pin is mapped to **GPIO 139** (labeled as PWM15_M1 in documentation), which we utilize for interrupt-driven RPM counting.

## 📊 Default Speed Curve
*   **Up to 40°C**: Level 1 (~1215 RPM)
*   **40°C to 50°C**: Level 2 (~2050 RPM)
*   **50°C to 60°C**: Level 3 (~2650 RPM)
*   **Over 60°C**: Level 4 (~3050 RPM)

## 📂 Included Configuration Files
For advanced users or those building custom kernels, we include the Device Tree Source and Overlay used to enable the PWM hardware:
*   `rock-5-itx-pwm14.dts`: The source code enabling the PWM14 node status to "okay".
*   `rockchip-rk3588-pwm14.dtbo`: The compiled binary overlay.

> **Note**: These are reference files. The installer script manages the necessary system configuration automatically.

## 🚀 Installation

### 1. Close the Repo
```bash
git clone https://github.com/[YOUR_USERNAME]/rock5-itx-fan-control.git
cd rock5-itx-fan-control
```

### 2. Run the Installer
```bash
sudo ./install.sh
```

## 📈 Monitoring
You can watch your fan temperature and RPM in real-time:
```bash
sudo journalctl -u rock5-fan.service -f
```

## 🧪 Manual Testing
Run a one-time cycle test to verify all speeds:
```bash
sudo /usr/local/bin/rock5-fan-control.py --test
```


## 🤖 Attribution
This repository was generated and structured with the assistance of **Antigravity with Gemini 3 Pro (High)** to accelerate development time.

<p align="center">
  <a href="https://ko-fi.com/R6R81SBTTL">
    <img src="https://ko-fi.com/img/githubbutton_sm.svg" alt="ko-fi" />
  </a>
</p>
