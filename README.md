# Smart Blind Stick for the Visually Impaired 🦯

An assistive IoT solution combining ESP8266 (NodeMCU) ultrasonic sensor hardware with a Python desktop service that provides instant audible voice warnings and an interactive live web telemetry dashboard.

## 🌟 Features

- **Hardware Obstacle Reflex**: Low-latency buzzer on the NodeMCU sounds immediately when an object is detected within threshold range.
- **Audible Voice Guidance**: Natural text-to-speech engine announces obstacle distance dynamically (e.g. *"Obstacle ahead, 45 centimeters"*).
- **Live Web Dashboard**: Browser-based real-time telemetry viewer (running on http://localhost:8000) visualizing distance trends and sensor diagnostics.
- **Dual Mode Operation**:
  - serial: Real hardware telemetry via NodeMCU USB serial.
  - sim: Interactive slider simulation mode without requiring physical hardware connected.

## 🛠️ Pin Configuration (NodeMCU ESP8266)

| Component | Pin | GPIO |
|---|---|---|
| HC-SR04 Trig | D1 | GPIO 5 |
| HC-SR04 Echo | D2 | GPIO 4 |
| Buzzer (+) | D5 | GPIO 14 |
| Buzzer (-) & Sensor GND | GND | GND |
| HC-SR04 VCC | Vin / 5V | 5V |

## 🚀 Getting Started

1. **Flash Firmware**:
   - Open smart_stick.ino in Arduino IDE.
   - Select Board: **NodeMCU 1.0 (ESP-12E Module)**.
   - Upload sketch at 115200 baud.

2. **Run Python Dashboard & Voice Engine**:
   `ash
   pip install pyserial
   python smart_stick.py
   `
   Open http://localhost:8000 to view the live dashboard.
