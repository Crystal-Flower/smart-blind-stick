/*
 * Smart Stick - NodeMCU (ESP8266) Ultrasonic & Buzzer Sketch
 * Baud rate: 115200 (matches smart_stick.py)
 *
 * Pin Connections:
 *  - HC-SR04 Trig Pin -> D1 (GPIO 5)
 *  - HC-SR04 Echo Pin -> D2 (GPIO 4)
 *  - Buzzer Positive  -> D5 (GPIO 14)
 *  - Buzzer Negative  -> GND
 *  - HC-SR04 VCC      -> Vin (5V) or 3.3V
 *  - HC-SR04 GND      -> GND
 */

const int TRIG_PIN = D1;      // GPIO 5
const int ECHO_PIN = D2;      // GPIO 4
const int BUZZER_PIN = D5;    // GPIO 14

const float THRESHOLD_CM = 5.0; // Buzzer alert distance threshold

void setup() {
  Serial.begin(115200);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);
  delay(500);
  Serial.println("Smart Stick Initialized.");
}

void loop() {
  // Clear the trigger pin
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);

  // Send a 10us trigger pulse
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  // Read the echo pin pulse duration in microseconds (timeout ~30ms = ~5m max)
  long duration = pulseIn(ECHO_PIN, HIGH, 30000);

  if (duration == 0) {
    Serial.println("Distance: No echo");
    digitalWrite(BUZZER_PIN, LOW);
  } else {
    // Speed of sound = 343 m/s = 0.0343 cm/us -> distance = (duration * 0.0343) / 2
    float distance = (duration * 0.0343) / 2.0;

    // Send formatted reading parsed by smart_stick.py
    Serial.print("Distance: ");
    Serial.print(distance, 1);
    Serial.println(" cm");

    // Activate buzzer if within close range
    if (distance <= THRESHOLD_CM && distance > 0.5) {
      digitalWrite(BUZZER_PIN, HIGH);
    } else {
      digitalWrite(BUZZER_PIN, LOW);
    }
  }

  delay(100); // 10Hz sampling rate
}
