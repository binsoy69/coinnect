#include <TamperFilter.h>
#include <Arduino.h>
#include <PinChangeInterrupt.h>

// Standalone SW-420 shock sensor bench test for Coinnect Uno wiring.
// The SW-420 sensing element is configured so that the module DO output
// idles LOW and rises HIGH when vibration/tamper is detected (active-high).

static const uint8_t SHOCK_A_PIN = 3;   // INT1 on Uno, active-high DO
static const uint8_t SHOCK_B_PIN = A0;  // PCINT8 on Uno (Analog A0), active-high DO
static const unsigned long STATUS_INTERVAL_MS = 2000;

static volatile TamperFilter tamperFilter;

static volatile bool securityArmed = false; // Mimics production boot state (disarmed)
static bool tamperLatched = false; // Mimics production boot state (unlatched)
static unsigned long lastStatusMs = 0;
static String inputBuffer = "";

void shockAISR() {
  if (securityArmed) tamperFilter.pulse(0, millis());
}

void shockBISR() {
  if (securityArmed) tamperFilter.pulse(1, millis());
}

// Change listening state and clear history atomically with respect to both ISRs.
void setSecurityArmed(bool armed) {
  noInterrupts();
  securityArmed = armed;
  tamperFilter.clear();
  interrupts();
}

void printStatus() {
  Serial.print(F("--- STATUS ["));
  Serial.print(securityArmed ? "ARMED" : "DISARMED");
  Serial.print(F("] --- "));
  if (tamperLatched) {
    Serial.print(F("!!! LOCKED_OUT (TAMPER LATCHED) !!!"));
  } else {
    Serial.print(F("SYSTEM OK"));
  }
  Serial.print(F(" | PIN LEVELS: A (D3) = "));
  Serial.print(digitalRead(SHOCK_A_PIN) == HIGH ? "HIGH (triggered)" : "LOW (idle)");
  Serial.print(F(", B (A0) = "));
  Serial.println(digitalRead(SHOCK_B_PIN) == HIGH ? "HIGH (triggered)" : "LOW (idle)");
}

void handleTamper(const char *sensor) {
  if (tamperLatched) return;
  tamperLatched = true;
  Serial.print(F("!!! SECURITY ALERT: TAMPER "));
  Serial.print(sensor);
  Serial.println(F(" DETECTED! Entering LOCKDOWN state !!!"));
  printStatus();
}

void serviceShockEvents() {
  noInterrupts();
  if (!securityArmed) tamperFilter.clear();
  tamperFilter.expire(millis());
  const uint8_t confirmed = tamperFilter.confirmed;
  const bool pending = tamperFilter.pending;
  interrupts();

  static bool wasPending = false;
  if (pending && !wasPending) Serial.println(F("TAMPER PENDING: sustained pulses required"));
  if (!pending && wasPending && !confirmed) Serial.println(F("TAMPER EXPIRED/CLEARED"));
  wasPending = pending;
  if (confirmed && !tamperLatched) handleTamper(confirmed == 1 ? "A" : "B");
}

void handleSerialCommand(String cmd) {
  cmd.trim();
  cmd.toLowerCase();
  
  if (cmd.length() == 0) return;

  if (cmd == "lock") {
    setSecurityArmed(true);
    Serial.println(F("CMD: arming security (SECURITY_LOCK)"));
    printStatus();
  } 
  else if (cmd == "unlock") {
    setSecurityArmed(false);
    Serial.println(F("CMD: disarming security (SECURITY_UNLOCK)"));
    printStatus();
  } 
  else if (cmd == "reset") {
    noInterrupts();
    tamperFilter.clear();
    interrupts();
    tamperLatched = false;
    setSecurityArmed(true); // Mimics handleReset() in production firmware which arms the system
    Serial.println(F("CMD: system reset / cleared tamper latch (RESET)"));
    printStatus();
  } 
  else if (cmd == "status") {
    printStatus();
  } 
  else {
    Serial.print(F("Unknown command: '"));
    Serial.print(cmd);
    Serial.println(F("'. Available commands: 'lock', 'unlock', 'reset', 'status'"));
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

  Serial.println(F("=================================================="));
  Serial.println(F("Coinnect Uno Shock Sensor Bench Test (Active-High)"));
  Serial.println(F("Mimics Production Security State Machine (Disarmed on boot)"));
  Serial.println(F("=================================================="));
  Serial.println(F("Requires pulses spanning 3000 ms; gaps over 750 ms restart detection."));
  Serial.println(F("Available serial commands:"));
  Serial.println(F("  'lock'   - Arm the shock sensors (mimics SECURITY_LOCK)"));
  Serial.println(F("  'unlock' - Disarm the shock sensors (mimics SECURITY_UNLOCK)"));
  Serial.println(F("  'reset'  - Clear tamper lockout and arm (mimics RESET)"));
  Serial.println(F("  'status' - Print current system and pin states"));
  Serial.println(F("=================================================="));
  
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
