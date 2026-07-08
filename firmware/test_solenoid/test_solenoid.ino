#include <Arduino.h>

// Standalone solenoid relay bench test for Coinnect Mega #2 wiring.
// The sketch boots locked/off and only energizes the relay after Serial input.

static const uint8_t SOLENOID_PIN = A5;
static const uint8_t LED_RED_PIN = 22;
static const uint8_t LED_GREEN_PIN = 23;

static const uint8_t LOCK_RELAY_LOCKED_LEVEL = LOW;
static const uint8_t LOCK_RELAY_UNLOCKED_LEVEL = HIGH;
static const unsigned long DEFAULT_PULSE_MS = 1000;

static bool doorLocked = true;
static String inputLine;

void printHelp() {
  Serial.println("Commands: LOCK, UNLOCK, PULSE, STATUS, HELP");
  Serial.println("LOCK: A5 (D19) LOW, red LED on, green LED off");
  Serial.println("UNLOCK: A5 (D19) HIGH, red LED off, green LED on");
  Serial.println("PULSE: A5 (D19) HIGH briefly, then locked/off");
}

void setLocked(bool locked) {
  doorLocked = locked;
  if (locked) {
    digitalWrite(SOLENOID_PIN, LOCK_RELAY_LOCKED_LEVEL);
    digitalWrite(LED_RED_PIN, HIGH);
    digitalWrite(LED_GREEN_PIN, LOW);
  } else {
    digitalWrite(SOLENOID_PIN, LOCK_RELAY_UNLOCKED_LEVEL);
    digitalWrite(LED_RED_PIN, LOW);
    digitalWrite(LED_GREEN_PIN, HIGH);
  }
}

void printStatus() {
  Serial.print("STATUS locked=");
  Serial.print(doorLocked ? "true" : "false");
  Serial.print(" A5=");
  Serial.println(digitalRead(SOLENOID_PIN) == HIGH ? "HIGH" : "LOW");
}

void pulseSolenoid() {
  Serial.println("PULSE start");
  setLocked(false);
  delay(DEFAULT_PULSE_MS);
  setLocked(true);
  Serial.println("PULSE complete; locked/off");
}

void handleCommand(String command) {
  command.trim();
  command.toUpperCase();

  if (command.length() == 0) {
    return;
  }
  if (command == "LOCK") {
    setLocked(true);
    printStatus();
  } else if (command == "UNLOCK") {
    setLocked(false);
    printStatus();
  } else if (command == "PULSE") {
    pulseSolenoid();
    printStatus();
  } else if (command == "STATUS") {
    printStatus();
  } else if (command == "HELP") {
    printHelp();
  } else {
    Serial.print("Unknown command: ");
    Serial.println(command);
    printHelp();
  }
}

void setup() {
  Serial.begin(115200);
  while (!Serial) {
    ;
  }

  inputLine.reserve(64);
  pinMode(SOLENOID_PIN, OUTPUT);
  pinMode(LED_RED_PIN, OUTPUT);
  pinMode(LED_GREEN_PIN, OUTPUT);
  setLocked(true);

  Serial.println("Coinnect solenoid test");
  printHelp();
  printStatus();
}

void loop() {
  while (Serial.available() > 0) {
    const char c = static_cast<char>(Serial.read());
    if (c == '\n' || c == '\r') {
      handleCommand(inputLine);
      inputLine = "";
    } else if (inputLine.length() < 63) {
      inputLine += c;
    }
  }
}
