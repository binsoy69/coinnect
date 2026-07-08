#include <Arduino.h>
#include <ArduinoJson.h>
#include <Servo.h>
#include <SPI.h>
#include <MFRC522.h>
#include <PinChangeInterrupt.h>

// Coinnect Uno firmware: coin accept/dispense + security + RFID.
// Serial protocol: newline-delimited JSON at 115200 baud.

static const char *FIRMWARE_VERSION = "2.2.0-uno";
static const char *CONTROLLER_ID = "COIN_SECURITY";

// MFRC522 RFID reader pins.
static const uint8_t MFRC522_RST_PIN = A1;  // D15 on Uno
static const uint8_t MFRC522_SS_PIN = 10;  // Uno hardware SS pin

// Coin acceptor, sorter, and dispenser pins.
static const uint8_t COIN_PULSE_PIN = 2;  // INT0 on Uno
static const uint8_t COIN_SORTER_SERVO_PIN = 7;
static const uint8_t COIN_ACCEPTOR_ENABLE_PIN = 4;
static const uint8_t SERVO_PHP_1_PIN = 8;
static const uint8_t SERVO_PHP_5_PIN = 9;
static const uint8_t SERVO_PHP_10_PIN = 5;
static const uint8_t SERVO_PHP_20_PIN = 6;

// Security pins. SW-420 modules configured as active-high (idles LOW,
// rises HIGH when vibration/tamper is detected).
static const uint8_t SHOCK_A_PIN = 3;   // INT1 on Uno, active-high DO
static const uint8_t SHOCK_B_PIN = A0;  // PCINT8 on Uno (Analog A0), active-high DO
static const uint8_t SOLENOID_PIN = A5;  // D19 on Uno
static const uint8_t LED_RED_PIN = A3;   // D17 on Uno
static const uint8_t LED_GREEN_PIN = A4; // D18 on Uno

// Relay/indicator levels. Docs specify LOW = locked, HIGH = unlocked.
static const uint8_t LOCK_RELAY_LOCKED_LEVEL = LOW;
static const uint8_t LOCK_RELAY_UNLOCKED_LEVEL = HIGH;

// Servo defaults for prototype coin gates.
static const uint8_t SERVO_RESET_DEG = 0;
static const uint8_t SERVO_PUSH_DEG = 180;
static const unsigned long SERVO_STEP_TIME_MS = 1;
static const unsigned long SERVO_CYCLE_SETTLE_MS = 300;

// Three-position coin sorter servo.
static const uint8_t COIN_SORTER_CENTER_DEG = 81;
static const uint8_t COIN_SORTER_LEFT_DEG = 45;
static const uint8_t COIN_SORTER_RIGHT_DEG = 110;
static const unsigned long COIN_SORTER_SETTLE_MS = 250;
static const unsigned long COIN_SORTER_HOLD_MS = 500;

// Pulse train interpretation: value pulses. 1/5/10/20 pulses map to PHP value.
static const unsigned long COIN_PULSE_DEBOUNCE_MS = 15;
static const unsigned long COIN_TRAIN_DONE_MS = 150;
static const unsigned long TAMPER_DEBOUNCE_MS = 250;

Servo servoPhp1;
Servo servoPhp5;
Servo servoPhp10;
Servo servoPhp20;
Servo coinSorterServo;
MFRC522 mfrc522(MFRC522_SS_PIN, MFRC522_RST_PIN);

struct CoinDispenser {
  Servo *servo;
  int denom;
  bool pushToResetFirst;
};

static CoinDispenser coinDispensers[] = {
    {&servoPhp1, 1, true},
    {&servoPhp5, 5, false},
    {&servoPhp10, 10, false},
    {&servoPhp20, 20, true},
};

static const uint8_t COIN_DISPENSER_COUNT =
    sizeof(coinDispensers) / sizeof(coinDispensers[0]);

static String inputLine;
static bool doorLocked = true;
static bool tamperLatched = false;
static bool securityArmed = false; // Starts disarmed/not listening on boot
static volatile bool coinAcceptorEnabled = false;
static const char *coinSorterPosition = "CENTER";
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

void setDispenserRestPosition(uint8_t index) {
  CoinDispenser &dispenser = coinDispensers[index];
  dispenser.servo->write(dispenser.pushToResetFirst ? SERVO_PUSH_DEG
                                                     : SERVO_RESET_DEG);
}

uint8_t sorterAngleForPosition(const char *position) {
  if (strcmp(position, "LEFT") == 0) {
    return COIN_SORTER_LEFT_DEG;
  }
  if (strcmp(position, "RIGHT") == 0) {
    return COIN_SORTER_RIGHT_DEG;
  }
  return COIN_SORTER_CENTER_DEG;
}

bool isValidSorterPosition(const char *position) {
  return strcmp(position, "CENTER") == 0 || strcmp(position, "LEFT") == 0 ||
         strcmp(position, "RIGHT") == 0;
}

const char *sorterPositionForDenom(int denom) {
  if (denom == 1 || denom == 5) {
    return "RIGHT";
  }
  if (denom == 10 || denom == 20) {
    return "LEFT";
  }
  return "CENTER";
}

void setCoinSorterPosition(const char *position) {
  coinSorterPosition = position;
  coinSorterServo.write(sorterAngleForPosition(position));
  delay(COIN_SORTER_SETTLE_MS);
}

void clearCoinPulseTrain() {
  noInterrupts();
  coinPulseCount = 0;
  lastCoinPulseMs = 0;
  lastCoinInterruptMs = 0;
  interrupts();
}

void setCoinAcceptorEnabled(bool enabled) {
  coinAcceptorEnabled = enabled;
  digitalWrite(COIN_ACCEPTOR_ENABLE_PIN, enabled ? HIGH : LOW);
  if (!enabled) {
    clearCoinPulseTrain();
  }
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
  setCoinAcceptorEnabled(false);
  setCoinSorterPosition("CENTER");
  lockDoor(true);
  blinkTamperLed();
  sendTamperEvent(sensor);
}

void coinPulseISR() {
  if (!coinAcceptorEnabled) {
    return;
  }
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
  if (!securityArmed) {
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

void serviceCoinPulseTrain() {
  uint8_t pulses = 0;
  const unsigned long now = millis();

  if (!coinAcceptorEnabled) {
    clearCoinPulseTrain();
    return;
  }

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
  setCoinAcceptorEnabled(false);
  setCoinSorterPosition(sorterPositionForDenom(denom));
  sendCoinInEvent(denom);
  delay(COIN_SORTER_HOLD_MS);
  setCoinSorterPosition("CENTER");
  if (!tamperLatched) {
    setCoinAcceptorEnabled(true);
  }
}

bool dispenseSingleCoin(uint8_t dispenserIndex) {
  serviceTamperEvents();
  if (tamperLatched) {
    return false;
  }

  CoinDispenser &dispenser = coinDispensers[dispenserIndex];
  Servo *servo = dispenser.servo;
  if (dispenser.pushToResetFirst) {
    for (int pos = SERVO_PUSH_DEG; pos >= SERVO_RESET_DEG; pos--) {
      servo->write(pos);
      delay(SERVO_STEP_TIME_MS);
    }
    for (int pos = SERVO_RESET_DEG; pos <= SERVO_PUSH_DEG; pos++) {
      servo->write(pos);
      delay(SERVO_STEP_TIME_MS);
    }
  } else {
    for (int pos = SERVO_RESET_DEG; pos <= SERVO_PUSH_DEG; pos++) {
      servo->write(pos);
      delay(SERVO_STEP_TIME_MS);
    }
    for (int pos = SERVO_PUSH_DEG; pos >= SERVO_RESET_DEG; pos--) {
      servo->write(pos);
      delay(SERVO_STEP_TIME_MS);
    }
  }
  delay(SERVO_CYCLE_SETTLE_MS);
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
  securityArmed = true; // Armed during initialization/reconciliation
  setCoinAcceptorEnabled(false);
  setCoinSorterPosition("CENTER");
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

  setCoinAcceptorEnabled(false);
  setCoinSorterPosition("CENTER");

  StaticJsonDocument<96> doc;
  doc["status"] = "OK";
  doc["previous_total"] = previousTotal;
  sendDocument(doc);
}

void handleCoinAcceptorEnable(JsonDocument &cmdDoc) {
  if (!cmdDoc["enabled"].is<bool>()) {
    sendError("INVALID_PARAM");
    return;
  }

  const bool enabled = cmdDoc["enabled"];
  if (enabled && tamperLatched) {
    sendError("LOCKED_OUT");
    return;
  }

  setCoinAcceptorEnabled(enabled);

  StaticJsonDocument<96> doc;
  doc["status"] = "OK";
  doc["enabled"] = (bool)coinAcceptorEnabled;
  sendDocument(doc);
}

void handleCoinStatus() {
  StaticJsonDocument<160> doc;
  doc["status"] = "OK";
  doc["acceptor_enabled"] = (bool)coinAcceptorEnabled;
  doc["sorter_position"] = coinSorterPosition;
  doc["sorter_angle"] = sorterAngleForPosition(coinSorterPosition);
  doc["session_total"] = coinSessionTotal;
  sendDocument(doc);
}

void handleCoinSorterPosition(JsonDocument &cmdDoc) {
  const char *position = cmdDoc["position"] | "";
  if (!isValidSorterPosition(position)) {
    sendError("INVALID_PARAM");
    return;
  }

  setCoinSorterPosition(position);

  StaticJsonDocument<128> doc;
  doc["status"] = "OK";
  doc["sorter_position"] = coinSorterPosition;
  doc["sorter_angle"] = sorterAngleForPosition(coinSorterPosition);
  sendDocument(doc);
}

void handleSecurityLock() {
  securityArmed = true; // Armed/listening
  lockDoor(true);
  StaticJsonDocument<96> doc;
  doc["status"] = "OK";
  doc["locked"] = true;
  sendDocument(doc);
}

void handleSecurityUnlock() {
  securityArmed = false; // Disarmed/not listening
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
  } else if (strcmp(cmd, "COIN_ACCEPTOR_ENABLE") == 0) {
    handleCoinAcceptorEnable(cmdDoc);
  } else if (strcmp(cmd, "COIN_STATUS") == 0) {
    handleCoinStatus();
  } else if (strcmp(cmd, "COIN_SORTER_POSITION") == 0) {
    handleCoinSorterPosition(cmdDoc);
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
  coinSorterServo.attach(COIN_SORTER_SERVO_PIN);
  servoPhp1.attach(SERVO_PHP_1_PIN);
  servoPhp5.attach(SERVO_PHP_5_PIN);
  servoPhp10.attach(SERVO_PHP_10_PIN);
  servoPhp20.attach(SERVO_PHP_20_PIN);

  setCoinSorterPosition("CENTER");
  for (uint8_t i = 0; i < COIN_DISPENSER_COUNT; i++) {
    setDispenserRestPosition(i);
  }
  delay(300);
}

void setupSecurityPins() {
  // Active-high logic (idles LOW, rises HIGH). No pull-up needed.
  pinMode(SHOCK_A_PIN, INPUT);
  pinMode(SHOCK_B_PIN, INPUT);
  pinMode(SOLENOID_PIN, OUTPUT);
  pinMode(LED_RED_PIN, OUTPUT);
  pinMode(LED_GREEN_PIN, OUTPUT);
  lockDoor(false);
}

void setup() {
  Serial.begin(115200);
  inputLine.reserve(256);

  pinMode(COIN_PULSE_PIN, INPUT_PULLUP);
  pinMode(COIN_ACCEPTOR_ENABLE_PIN, OUTPUT);
  setCoinAcceptorEnabled(false);
  setupCoinServos();
  setupSecurityPins();

  SPI.begin();
  mfrc522.PCD_Init();

  attachInterrupt(digitalPinToInterrupt(COIN_PULSE_PIN), coinPulseISR, FALLING);
  // Tamper is detected when the active-high SW-420 module DO rises HIGH.
  attachInterrupt(digitalPinToInterrupt(SHOCK_A_PIN), shockAISR, RISING);
  
  // Attach PinChangeInterrupt to SHOCK_B_PIN using NicoHood's library
  attachPinChangeInterrupt(digitalPinToPinChangeInterrupt(SHOCK_B_PIN), shockBISR, RISING);

  delay(250);
  sendReadyEvent();
}

void serviceRFID() {
  if (!mfrc522.PICC_IsNewCardPresent()) {
    return;
  }
  if (!mfrc522.PICC_ReadCardSerial()) {
    return;
  }

  String uidStr = "";
  for (byte i = 0; i < mfrc522.uid.size; i++) {
    if (mfrc522.uid.uidByte[i] < 0x10) uidStr += "0";
    uidStr += String(mfrc522.uid.uidByte[i], HEX);
  }
  uidStr.toUpperCase();

  StaticJsonDocument<128> doc;
  doc["event"] = "RFID";
  doc["uid"] = uidStr;
  sendDocument(doc);

  mfrc522.PICC_HaltA();
  mfrc522.PCD_StopCrypto1();
}

void loop() {
  serviceTamperEvents();
  serviceCoinPulseTrain();
  serviceRFID();
  handleSerialInput();
}
