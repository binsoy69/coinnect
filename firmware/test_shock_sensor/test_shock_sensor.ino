#include <Arduino.h>
#include <PinChangeInterrupt.h>

// Standalone SW-420 shock sensor bench test for Coinnect Uno wiring.
// The SW-420 sensing element is configured so that the module DO output
// idles LOW and rises HIGH when vibration/tamper is detected (active-high).

static const uint8_t SHOCK_A_PIN = 3;   // INT1 on Uno, active-high DO
static const uint8_t SHOCK_B_PIN = A0;  // PCINT8 on Uno (Analog A0), active-high DO
static const unsigned long TAMPER_DEBOUNCE_MS = 250;
static const unsigned long STATUS_INTERVAL_MS = 2000;

static volatile bool shockAFlag = false;
static volatile bool shockBFlag = false;
static volatile unsigned long lastShockAMs = 0;
static volatile unsigned long lastShockBMs = 0;

static bool securityArmed = false; // Mimics production boot state (disarmed)
static bool tamperLatched = false; // Mimics production boot state (unlatched)
static unsigned long lastStatusMs = 0;
static String inputBuffer = "";

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

void printStatus() {
  Serial.print("--- STATUS [");
  Serial.print(securityArmed ? "ARMED" : "DISARMED");
  Serial.print("] --- ");
  if (tamperLatched) {
    Serial.print("!!! LOCKED_OUT (TAMPER LATCHED) !!!");
  } else {
    Serial.print("SYSTEM OK");
  }
  Serial.print(" | PIN LEVELS: A (D3) = ");
  Serial.print(digitalRead(SHOCK_A_PIN) == HIGH ? "HIGH (triggered)" : "LOW (idle)");
  Serial.print(", B (A0) = ");
  Serial.println(digitalRead(SHOCK_B_PIN) == HIGH ? "HIGH (triggered)" : "LOW (idle)");
}

void handleTamper(const char *sensor) {
  tamperLatched = true;
  Serial.print("!!! SECURITY ALERT: TAMPER ");
  Serial.print(sensor);
  Serial.println(" DETECTED! Entering LOCKDOWN state !!!");
  printStatus();
}

void serviceShockEvents() {
  if (!securityArmed) {
    // Mimics actual firmware: discard interrupt flags when security is disarmed
    noInterrupts();
    shockAFlag = false;
    shockBFlag = false;
    interrupts();
    return;
  }

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
    handleTamper("A");
  }
  if (b) {
    handleTamper("B");
  }
}

void handleSerialCommand(String cmd) {
  cmd.trim();
  cmd.toLowerCase();
  
  if (cmd.length() == 0) return;

  if (cmd == "lock") {
    securityArmed = true;
    Serial.println("CMD: arming security (SECURITY_LOCK)");
    printStatus();
  } 
  else if (cmd == "unlock") {
    securityArmed = false;
    Serial.println("CMD: disarming security (SECURITY_UNLOCK)");
    printStatus();
  } 
  else if (cmd == "reset") {
    noInterrupts();
    shockAFlag = false;
    shockBFlag = false;
    interrupts();
    tamperLatched = false;
    securityArmed = true; // Mimics handleReset() in production firmware which arms the system
    Serial.println("CMD: system reset / cleared tamper latch (RESET)");
    printStatus();
  } 
  else if (cmd == "status") {
    printStatus();
  } 
  else {
    Serial.print("Unknown command: '");
    Serial.print(cmd);
    Serial.println("'. Available commands: 'lock', 'unlock', 'reset', 'status'");
  }
}

void setup() {
  Serial.begin(115200);
  while (!Serial) {
    ;
  }

  pinMode(SHOCK_A_PIN, INPUT);
  pinMode(SHOCK_B_PIN, INPUT);
  
  attachInterrupt(digitalPinToInterrupt(SHOCK_A_PIN), shockAISR, RISING);
  // Attach PinChangeInterrupt to SHOCK_B_PIN using NicoHood's library
  attachPinChangeInterrupt(digitalPinToPinChangeInterrupt(SHOCK_B_PIN), shockBISR, RISING);

  Serial.println("==================================================");
  Serial.println("Coinnect Uno Shock Sensor Bench Test (Active-High)");
  Serial.println("Mimics Production Security State Machine (Disarmed on boot)");
  Serial.println("==================================================");
  Serial.println("Available serial commands:");
  Serial.println("  'lock'   - Arm the shock sensors (mimics SECURITY_LOCK)");
  Serial.println("  'unlock' - Disarm the shock sensors (mimics SECURITY_UNLOCK)");
  Serial.println("  'reset'  - Clear tamper lockout and arm (mimics RESET)");
  Serial.println("  'status' - Print current system and pin states");
  Serial.println("==================================================");
  
  printStatus();
}

void loop() {
  serviceShockEvents();

  // Read serial input for commands
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n') {
      handleSerialCommand(inputBuffer);
      inputBuffer = "";
    } else if (c != '\r') {
      inputBuffer += c;
    }
  }

  // Periodically print status to show levels without typing
  const unsigned long now = millis();
  if (now - lastStatusMs >= STATUS_INTERVAL_MS) {
    lastStatusMs = now;
    printStatus();
  }
}
