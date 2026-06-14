#include <Arduino.h>

// Standalone SW-420 shock sensor bench test for Coinnect Mega #2 wiring.
// The SW-420 sensing element is normally closed at rest, while the module DO
// output idles HIGH and falls LOW when vibration/tamper is detected.

static const uint8_t SHOCK_A_PIN = 19;  // INT4, production shock sensor A
static const uint8_t SHOCK_B_PIN = 20;  // INT3, production shock sensor B
static const unsigned long TAMPER_DEBOUNCE_MS = 250;
static const unsigned long STATUS_INTERVAL_MS = 1000;

static volatile bool shockAFlag = false;
static volatile bool shockBFlag = false;
static volatile unsigned long lastShockAMs = 0;
static volatile unsigned long lastShockBMs = 0;

static unsigned long lastStatusMs = 0;

void shockAISR() {
  const unsigned long now = millis();
  if (now - lastShockAMs >= TAMPER_DEBOUNCE_MS) {
    shockAFlag = true;
    lastShockAMs = now;
  }
}

void shockBISR() {
  const unsigned long now = millis();
  if (now - lastShockBMs >= TAMPER_DEBOUNCE_MS) {
    shockBFlag = true;
    lastShockBMs = now;
  }
}

void printLevels() {
  Serial.print("LEVELS A=");
  Serial.print(digitalRead(SHOCK_A_PIN) == HIGH ? "HIGH idle" : "LOW triggered");
  Serial.print(" B=");
  Serial.println(digitalRead(SHOCK_B_PIN) == HIGH ? "HIGH idle" : "LOW triggered");
}

void serviceShockEvents() {
  bool a = false;
  bool b = false;

  noInterrupts();
  if (shockAFlag) {
    a = true;
    shockAFlag = false;
  }
  if (shockBFlag) {
    b = true;
    shockBFlag = false;
  }
  interrupts();

  if (a) {
    Serial.println("TAMPER A: falling edge detected");
  }
  if (b) {
    Serial.println("TAMPER B: falling edge detected");
  }
}

void setup() {
  Serial.begin(115200);
  while (!Serial) {
    ;
  }

  pinMode(SHOCK_A_PIN, INPUT_PULLUP);
  pinMode(SHOCK_B_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(SHOCK_A_PIN), shockAISR, FALLING);
  attachInterrupt(digitalPinToInterrupt(SHOCK_B_PIN), shockBISR, FALLING);

  Serial.println("Coinnect shock sensor test");
  Serial.println("SW-420 module DO: HIGH idle/no vibration, LOW triggered");
  Serial.println("Watching D19=A and D20=B at 115200 baud");
  printLevels();
}

void loop() {
  serviceShockEvents();

  const unsigned long now = millis();
  if (now - lastStatusMs >= STATUS_INTERVAL_MS) {
    lastStatusMs = now;
    printLevels();
  }
}
