#include <Arduino.h>
#include <ArduinoJson.h>
#include <Servo.h>

// Coinnect Mega #2 firmware: coin accept/dispense + security.
// Serial protocol: newline-delimited JSON at 115200 baud.

static const char *FIRMWARE_VERSION = "2.0.0";
static const char *CONTROLLER_ID = "COIN_SECURITY";

// Coin acceptor and dispenser pins.
static const uint8_t COIN_PULSE_PIN = 18;  // INT5
static const uint8_t SERVO_PHP_1_PIN = 44;
static const uint8_t SERVO_PHP_5_PIN = 45;
static const uint8_t SERVO_PHP_10_PIN = 46;
static const uint8_t SERVO_PHP_20_PIN = 6;

// Security pins.
static const uint8_t SHOCK_A_PIN = 19;  // INT4
static const uint8_t SHOCK_B_PIN = 20;  // INT3
static const uint8_t SOLENOID_PIN = 21;
static const uint8_t LED_RED_PIN = 22;
static const uint8_t LED_GREEN_PIN = 23;

// Relay/indicator levels. Docs specify LOW = locked, HIGH = unlocked.
static const uint8_t LOCK_RELAY_LOCKED_LEVEL = LOW;
static const uint8_t LOCK_RELAY_UNLOCKED_LEVEL = HIGH;

// Servo defaults for prototype coin gates.
static const uint8_t SERVO_CLOSED_DEG = 0;
static const uint8_t SERVO_OPEN_DEG = 90;
static const unsigned long SERVO_OPEN_TIME_MS = 150;
static const unsigned long SERVO_SETTLE_TIME_MS = 100;

// Pulse train interpretation: value pulses. 1/5/10/20 pulses map to PHP value.
static const unsigned long COIN_PULSE_DEBOUNCE_MS = 15;
static const unsigned long COIN_TRAIN_DONE_MS = 150;
static const unsigned long TAMPER_DEBOUNCE_MS = 250;

Servo servoPhp1;
Servo servoPhp5;
Servo servoPhp10;
Servo servoPhp20;

struct CoinDispenser {
  Servo *servo;
  int denom;
};

static CoinDispenser coinDispensers[] = {
    {&servoPhp1, 1},
    {&servoPhp5, 5},
    {&servoPhp10, 10},
    {&servoPhp20, 20},
};

static const uint8_t COIN_DISPENSER_COUNT =
    sizeof(coinDispensers) / sizeof(coinDispensers[0]);

static String inputLine;
static bool doorLocked = true;
static bool tamperLatched = false;
static int coinSessionTotal = 0;

static volatile uint8_t coinPulseCount = 0;
static volatile unsigned long lastCoinPulseMs = 0;
static volatile unsigned long lastCoinInterruptMs = 0;

static volatile bool shockAFlag = false;
static volatile bool shockBFlag = false;
static volatile unsigned long lastShockAMs = 0;
static volatile unsigned long lastShockBMs = 0;

void sendDocument(JsonDocument &doc) {
  serializeJson(doc, Serial);
  Serial.println();
}

void sendReadyEvent() {
  StaticJsonDocument<128> doc;
  doc["event"] = "READY";
  doc["version"] = FIRMWARE_VERSION;
  doc["controller"] = CONTROLLER_ID;
  sendDocument(doc);
}

void sendDoorStateEvent() {
  StaticJsonDocument<96> doc;
  doc["event"] = "DOOR_STATE";
  doc["locked"] = doorLocked;
  sendDocument(doc);
}

void sendTamperEvent(const char *sensor) {
  StaticJsonDocument<96> doc;
  doc["event"] = "TAMPER";
  doc["sensor"] = sensor;
  sendDocument(doc);
}

void sendCoinInEvent(int denom) {
  StaticJsonDocument<128> doc;
  doc["event"] = "COIN_IN";
  doc["denom"] = denom;
  doc["total"] = coinSessionTotal;
  sendDocument(doc);
}

void sendError(const char *code, int dispensed = -1) {
  StaticJsonDocument<128> doc;
  doc["status"] = "ERROR";
  doc["code"] = code;
  if (dispensed >= 0) {
    doc["dispensed"] = dispensed;
  }
  sendDocument(doc);
}

bool isValidCoinDenom(int denom) {
  return denom == 1 || denom == 5 || denom == 10 || denom == 20;
}

int findCoinDispenser(int denom) {
  for (uint8_t i = 0; i < COIN_DISPENSER_COUNT; i++) {
    if (coinDispensers[i].denom == denom) {
      return i;
    }
  }
  return -1;
}

void setServoClosed(uint8_t index) {
  coinDispensers[index].servo->write(SERVO_CLOSED_DEG);
}

void lockDoor(bool emitEvent) {
  digitalWrite(SOLENOID_PIN, LOCK_RELAY_LOCKED_LEVEL);
  digitalWrite(LED_RED_PIN, HIGH);
  digitalWrite(LED_GREEN_PIN, LOW);
  doorLocked = true;
  if (emitEvent) {
    sendDoorStateEvent();
  }
}

void unlockDoor(bool emitEvent) {
  digitalWrite(SOLENOID_PIN, LOCK_RELAY_UNLOCKED_LEVEL);
  digitalWrite(LED_RED_PIN, LOW);
  digitalWrite(LED_GREEN_PIN, HIGH);
  doorLocked = false;
  if (emitEvent) {
    sendDoorStateEvent();
  }
}

void blinkTamperLed() {
  for (uint8_t i = 0; i < 6; i++) {
    digitalWrite(LED_RED_PIN, LOW);
    delay(80);
    digitalWrite(LED_RED_PIN, HIGH);
    delay(80);
  }
}

void handleTamper(const char *sensor) {
  tamperLatched = true;
  lockDoor(true);
  blinkTamperLed();
  sendTamperEvent(sensor);
}

void coinPulseISR() {
  const unsigned long now = millis();
  if (now - lastCoinInterruptMs >= COIN_PULSE_DEBOUNCE_MS) {
    if (coinPulseCount < 250) {
      coinPulseCount++;
    }
    lastCoinPulseMs = now;
    lastCoinInterruptMs = now;
  }
}

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

void serviceTamperEvents() {
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

void serviceCoinPulseTrain() {
  uint8_t pulses = 0;
  const unsigned long now = millis();

  noInterrupts();
  const bool trainReady =
      coinPulseCount > 0 && (now - lastCoinPulseMs >= COIN_TRAIN_DONE_MS);
  if (trainReady) {
    pulses = coinPulseCount;
    coinPulseCount = 0;
  }
  interrupts();

  if (pulses == 0) {
    return;
  }

  const int denom = (int)pulses;
  if (!isValidCoinDenom(denom)) {
    return;
  }

  coinSessionTotal += denom;
  sendCoinInEvent(denom);
}

bool dispenseSingleCoin(uint8_t dispenserIndex) {
  serviceTamperEvents();
  if (tamperLatched) {
    return false;
  }

  Servo *servo = coinDispensers[dispenserIndex].servo;
  servo->write(SERVO_OPEN_DEG);
  delay(SERVO_OPEN_TIME_MS);
  servo->write(SERVO_CLOSED_DEG);
  delay(SERVO_SETTLE_TIME_MS);
  return !tamperLatched;
}

int dispenseCoinsByDenom(int denom, int count, const char **errorCode) {
  *errorCode = nullptr;
  const int dispenserIndex = findCoinDispenser(denom);
  if (dispenserIndex < 0) {
    *errorCode = "INVALID_DENOM";
    return 0;
  }

  int dispensed = 0;
  for (int i = 0; i < count; i++) {
    if (!dispenseSingleCoin((uint8_t)dispenserIndex)) {
      *errorCode = "LOCKED_OUT";
      return dispensed;
    }
    dispensed++;
  }
  return dispensed;
}

void calculateCoinBreakdown(int amount, int &c20, int &c10, int &c5, int &c1) {
  c20 = amount / 20;
  amount %= 20;
  c10 = amount / 10;
  amount %= 10;
  c5 = amount / 5;
  amount %= 5;
  c1 = amount;
}

void handlePing() {
  StaticJsonDocument<128> doc;
  doc["status"] = "OK";
  doc["message"] = "PONG";
  sendDocument(doc);
}

void handleVersion() {
  StaticJsonDocument<128> doc;
  doc["status"] = "OK";
  doc["version"] = FIRMWARE_VERSION;
  doc["controller"] = CONTROLLER_ID;
  sendDocument(doc);
}

void handleReset() {
  noInterrupts();
  coinPulseCount = 0;
  shockAFlag = false;
  shockBFlag = false;
  interrupts();

  coinSessionTotal = 0;
  tamperLatched = false;
  lockDoor(true);

  StaticJsonDocument<64> doc;
  doc["status"] = "OK";
  sendDocument(doc);
}

void handleCoinDispense(JsonDocument &cmdDoc) {
  const int denom = cmdDoc["denom"] | 0;
  const int count = cmdDoc["count"] | 0;

  if (!isValidCoinDenom(denom)) {
    sendError("INVALID_DENOM");
    return;
  }
  if (count < 1 || count > 50) {
    sendError("INVALID_COUNT");
    return;
  }
  if (tamperLatched) {
    sendError("LOCKED_OUT", 0);
    return;
  }

  const char *errorCode = nullptr;
  const int dispensed = dispenseCoinsByDenom(denom, count, &errorCode);
  if (errorCode != nullptr) {
    sendError(errorCode, dispensed);
    return;
  }

  StaticJsonDocument<96> doc;
  doc["status"] = "OK";
  doc["dispensed"] = dispensed;
  sendDocument(doc);
}

void handleCoinChange(JsonDocument &cmdDoc) {
  const int amount = cmdDoc["amount"] | 0;
  if (amount < 1) {
    sendError("INVALID_COUNT");
    return;
  }
  if (tamperLatched) {
    sendError("LOCKED_OUT", 0);
    return;
  }

  int c20 = 0;
  int c10 = 0;
  int c5 = 0;
  int c1 = 0;
  calculateCoinBreakdown(amount, c20, c10, c5, c1);

  const char *errorCode = nullptr;
  int dispensed = 0;
  dispensed += dispenseCoinsByDenom(20, c20, &errorCode);
  if (errorCode == nullptr) {
    dispensed += dispenseCoinsByDenom(10, c10, &errorCode);
  }
  if (errorCode == nullptr) {
    dispensed += dispenseCoinsByDenom(5, c5, &errorCode);
  }
  if (errorCode == nullptr) {
    dispensed += dispenseCoinsByDenom(1, c1, &errorCode);
  }
  if (errorCode != nullptr) {
    sendError(errorCode, dispensed);
    return;
  }

  StaticJsonDocument<160> doc;
  doc["status"] = "OK";
  JsonObject breakdown = doc.createNestedObject("breakdown");
  if (c20 > 0) {
    breakdown["20"] = c20;
  }
  if (c10 > 0) {
    breakdown["10"] = c10;
  }
  if (c5 > 0) {
    breakdown["5"] = c5;
  }
  if (c1 > 0) {
    breakdown["1"] = c1;
  }
  sendDocument(doc);
}

void handleCoinReset() {
  const int previousTotal = coinSessionTotal;
  coinSessionTotal = 0;

  noInterrupts();
  coinPulseCount = 0;
  interrupts();

  StaticJsonDocument<96> doc;
  doc["status"] = "OK";
  doc["previous_total"] = previousTotal;
  sendDocument(doc);
}

void handleSecurityLock() {
  lockDoor(true);
  StaticJsonDocument<96> doc;
  doc["status"] = "OK";
  doc["locked"] = true;
  sendDocument(doc);
}

void handleSecurityUnlock() {
  unlockDoor(true);
  StaticJsonDocument<96> doc;
  doc["status"] = "OK";
  doc["locked"] = false;
  sendDocument(doc);
}

void handleSecurityStatus() {
  StaticJsonDocument<128> doc;
  doc["status"] = "OK";
  doc["locked"] = doorLocked;
  doc["tamper_a"] = tamperLatched;
  sendDocument(doc);
}

void dispatchCommand(const String &line) {
  StaticJsonDocument<384> cmdDoc;
  DeserializationError err = deserializeJson(cmdDoc, line);
  if (err) {
    sendError("PARSE_ERROR");
    return;
  }

  const char *cmd = cmdDoc["cmd"] | "";
  if (strcmp(cmd, "PING") == 0) {
    handlePing();
  } else if (strcmp(cmd, "VERSION") == 0) {
    handleVersion();
  } else if (strcmp(cmd, "RESET") == 0) {
    handleReset();
  } else if (strcmp(cmd, "COIN_DISPENSE") == 0) {
    handleCoinDispense(cmdDoc);
  } else if (strcmp(cmd, "COIN_CHANGE") == 0) {
    handleCoinChange(cmdDoc);
  } else if (strcmp(cmd, "COIN_RESET") == 0) {
    handleCoinReset();
  } else if (strcmp(cmd, "SECURITY_LOCK") == 0) {
    handleSecurityLock();
  } else if (strcmp(cmd, "SECURITY_UNLOCK") == 0) {
    handleSecurityUnlock();
  } else if (strcmp(cmd, "SECURITY_STATUS") == 0) {
    handleSecurityStatus();
  } else {
    sendError("UNKNOWN_CMD");
  }
}

void handleSerialInput() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n') {
      inputLine.trim();
      if (inputLine.length() > 0) {
        dispatchCommand(inputLine);
      }
      inputLine = "";
    } else if (c != '\r') {
      inputLine += c;
      if (inputLine.length() > 512) {
        inputLine = "";
        sendError("PARSE_ERROR");
      }
    }
  }
}

void setupCoinServos() {
  servoPhp1.attach(SERVO_PHP_1_PIN);
  servoPhp5.attach(SERVO_PHP_5_PIN);
  servoPhp10.attach(SERVO_PHP_10_PIN);
  servoPhp20.attach(SERVO_PHP_20_PIN);

  for (uint8_t i = 0; i < COIN_DISPENSER_COUNT; i++) {
    setServoClosed(i);
  }
  delay(300);
}

void setupSecurityPins() {
  pinMode(SHOCK_A_PIN, INPUT_PULLUP);
  pinMode(SHOCK_B_PIN, INPUT_PULLUP);
  pinMode(SOLENOID_PIN, OUTPUT);
  pinMode(LED_RED_PIN, OUTPUT);
  pinMode(LED_GREEN_PIN, OUTPUT);
  lockDoor(false);
}

void setup() {
  Serial.begin(115200);
  inputLine.reserve(256);

  pinMode(COIN_PULSE_PIN, INPUT_PULLUP);
  setupCoinServos();
  setupSecurityPins();

  attachInterrupt(digitalPinToInterrupt(COIN_PULSE_PIN), coinPulseISR, FALLING);
  attachInterrupt(digitalPinToInterrupt(SHOCK_A_PIN), shockAISR, FALLING);
  attachInterrupt(digitalPinToInterrupt(SHOCK_B_PIN), shockBISR, FALLING);

  delay(250);
  sendReadyEvent();
}

void loop() {
  serviceTamperEvents();
  serviceCoinPulseTrain();
  handleSerialInput();
}
