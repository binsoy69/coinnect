#include <Arduino.h>
#include <ArduinoJson.h>
#include <AccelStepper.h>

// Coinnect Mega #1 firmware: bill sorting + bill dispensing.
// Serial protocol: newline-delimited JSON at 115200 baud.

static const char *FIRMWARE_VERSION = "2.0.0";
static const char *CONTROLLER_ID = "BILL";

// Stepper / A4988 pins.
static const uint8_t STEP_PIN = 2;
static const uint8_t DIR_PIN = 3;
static const uint8_t ENABLE_PIN = 4;
static const uint8_t LIMIT_PIN = 5;

// A4988 enable is active LOW. Negative speed is the documented home direction.
static const long HOME_SPEED_STEPS_PER_SEC = -2500;
static const long HOME_BACKOFF_STEPS = 800;
static const unsigned long HOME_TIMEOUT_MS = 12000;
static const unsigned long SORT_TIMEOUT_MS = 12000;
static const float SORT_MAX_SPEED = 8000.0;
static const float SORT_ACCELERATION = 5000.0;
static const bool HOLD_SORTER_AFTER_MOVE = true;

// Bill dispenser timing.
static const unsigned long PUSHER_DURATION_MS = 200;
static const uint8_t DISPENSE_RETRY_ATTEMPTS = 5;
static const unsigned long ROLLER_SPINUP_MS = 500;
static const unsigned long IR_DETECT_TIMEOUT_MS = 1000;
static const unsigned long BILL_CLEAR_TIMEOUT_MS = 1000;
static const unsigned long ROLLER_EXTRA_MS = 300;
static const unsigned long INTER_BILL_DELAY_MS = 100;

static const uint8_t NO_PIN = 255;

struct DispenserUnit {
  uint8_t motorAIn1;
  uint8_t motorAIn2;
  uint8_t motorBIn3;
  uint8_t motorBIn4;
  uint8_t irSensorPin;
  const char *denom;
};

// Canonical pin map from reference/09_pin_assignments.md.
static DispenserUnit dispensers[] = {
    {22, 23, 24, 25, A0, "PHP_20"},
    {26, 27, 28, 29, A1, "PHP_50"},
    {30, 31, 32, 33, A2, "PHP_100"},
    {34, 35, 36, 37, A3, "PHP_200"},
    {38, 39, 40, 41, A4, "PHP_500"},
    {42, 43, 44, 45, A5, "PHP_1000"},
    {46, 47, 48, 49, A6, "USD_10"},
    {50, 51, 52, 53, A7, "USD_50"},
    {A8, A9, A10, A11, 14, "USD_100"},
    {A12, A13, A14, A15, 15, "EUR_5"},
    {7, 8, 9, 10, 16, "EUR_10"},
    {11, 12, 13, NO_PIN, 17, "EUR_20"},
};

static const uint8_t DISPENSER_COUNT = sizeof(dispensers) / sizeof(dispensers[0]);

struct SortSlotMap {
  const char *denom;
  uint8_t slot;
};

static const SortSlotMap sortSlotMap[] = {
    {"PHP_20", 1},   {"PHP_50", 2},   {"PHP_100", 3},
    {"PHP_200", 4},  {"PHP_500", 5},  {"PHP_1000", 6},
    {"USD_10", 7},   {"USD_50", 7},   {"USD_100", 7},
    {"EUR_5", 8},    {"EUR_10", 8},   {"EUR_20", 8},
};

static const long SLOT_POSITIONS[] = {
    2920, 8760, 14600, 20440, 26280, 32120, 37960, 43800,
};

AccelStepper sorter(AccelStepper::DRIVER, STEP_PIN, DIR_PIN);

static String inputLine;
static bool sorterHomed = false;
static bool sorterHomeFailed = false;
static int currentSlot = 0;

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

void sendError(const char *code, int dispensed = -1) {
  StaticJsonDocument<128> doc;
  doc["status"] = "ERROR";
  doc["code"] = code;
  if (dispensed >= 0) {
    doc["dispensed"] = dispensed;
  }
  sendDocument(doc);
}

void enableStepper() {
  digitalWrite(ENABLE_PIN, LOW);
}

void disableStepperIfAllowed() {
  if (!HOLD_SORTER_AFTER_MOVE) {
    digitalWrite(ENABLE_PIN, HIGH);
  }
}

bool limitTriggered() {
  return digitalRead(LIMIT_PIN) == LOW;
}

void setPinLowIfPresent(uint8_t pin) {
  if (pin != NO_PIN) {
    digitalWrite(pin, LOW);
  }
}

void setPinHighIfPresent(uint8_t pin) {
  if (pin != NO_PIN) {
    digitalWrite(pin, HIGH);
  }
}

void stopMotorA(uint8_t unitIndex) {
  setPinLowIfPresent(dispensers[unitIndex].motorAIn1);
  setPinLowIfPresent(dispensers[unitIndex].motorAIn2);
}

void stopMotorB(uint8_t unitIndex) {
  setPinLowIfPresent(dispensers[unitIndex].motorBIn3);
  setPinLowIfPresent(dispensers[unitIndex].motorBIn4);
}

void stopAllDispensers() {
  for (uint8_t i = 0; i < DISPENSER_COUNT; i++) {
    stopMotorA(i);
    stopMotorB(i);
  }
}

void motorAForward(uint8_t unitIndex) {
  setPinHighIfPresent(dispensers[unitIndex].motorAIn1);
  setPinLowIfPresent(dispensers[unitIndex].motorAIn2);
}

void motorBForward(uint8_t unitIndex) {
  setPinHighIfPresent(dispensers[unitIndex].motorBIn3);
  setPinLowIfPresent(dispensers[unitIndex].motorBIn4);
}

bool isBillDetected(uint8_t unitIndex) {
  return digitalRead(dispensers[unitIndex].irSensorPin) == LOW;
}

bool waitForBillDetected(uint8_t unitIndex, unsigned long timeoutMs) {
  const unsigned long startedAt = millis();
  while (millis() - startedAt < timeoutMs) {
    if (isBillDetected(unitIndex)) {
      return true;
    }
    delay(10);
  }
  return false;
}

bool waitForBillCleared(uint8_t unitIndex, unsigned long timeoutMs) {
  const unsigned long startedAt = millis();
  while (millis() - startedAt < timeoutMs) {
    if (!isBillDetected(unitIndex)) {
      return true;
    }
    delay(10);
  }
  return false;
}

int findDispenserIndex(const char *denom) {
  if (denom == nullptr) {
    return -1;
  }
  for (uint8_t i = 0; i < DISPENSER_COUNT; i++) {
    if (strcmp(dispensers[i].denom, denom) == 0) {
      return i;
    }
  }
  return -1;
}

int slotForDenom(const char *denom) {
  if (denom == nullptr) {
    return -1;
  }
  const uint8_t mapCount = sizeof(sortSlotMap) / sizeof(sortSlotMap[0]);
  for (uint8_t i = 0; i < mapCount; i++) {
    if (strcmp(sortSlotMap[i].denom, denom) == 0) {
      return sortSlotMap[i].slot;
    }
  }
  return -1;
}

bool homeSorter() {
  sorterHomeFailed = false;
  enableStepper();
  sorter.setMaxSpeed(abs(HOME_SPEED_STEPS_PER_SEC));
  sorter.setAcceleration(SORT_ACCELERATION);
  sorter.setSpeed(HOME_SPEED_STEPS_PER_SEC);

  const unsigned long startedAt = millis();
  while (!limitTriggered()) {
    sorter.runSpeed();
    if (millis() - startedAt > HOME_TIMEOUT_MS) {
      sorter.stop();
      digitalWrite(ENABLE_PIN, HIGH);
      sorterHomed = false;
      sorterHomeFailed = true;
      currentSlot = 0;
      return false;
    }
  }

  sorter.stop();
  sorter.setCurrentPosition(0);
  sorter.moveTo(HOME_BACKOFF_STEPS);
  while (sorter.distanceToGo() != 0) {
    sorter.run();
  }

  sorter.setCurrentPosition(0);
  sorterHomed = true;
  sorterHomeFailed = false;
  currentSlot = 0;
  disableStepperIfAllowed();
  return true;
}

bool moveSorterToSlot(uint8_t slot) {
  if (!sorterHomed || slot < 1 || slot > 8) {
    return false;
  }

  const long targetPosition = SLOT_POSITIONS[slot - 1];
  enableStepper();
  sorter.setMaxSpeed(SORT_MAX_SPEED);
  sorter.setAcceleration(SORT_ACCELERATION);
  sorter.moveTo(targetPosition);

  const unsigned long startedAt = millis();
  while (sorter.distanceToGo() != 0) {
    sorter.run();
    if (millis() - startedAt > SORT_TIMEOUT_MS) {
      sorter.stop();
      currentSlot = 0;
      return false;
    }
  }

  currentSlot = slot;
  disableStepperIfAllowed();
  return true;
}

int dispenseBills(uint8_t unitIndex, int count, const char **errorCode) {
  int dispensed = 0;
  *errorCode = nullptr;

  // L298N ENA/ENB are held HIGH with hardware jumpers; firmware drives IN1-IN4 only.
  motorBForward(unitIndex);
  delay(ROLLER_SPINUP_MS);

  for (int i = 0; i < count; i++) {
    bool detected = false;

    for (uint8_t attempt = 0; attempt < DISPENSE_RETRY_ATTEMPTS; attempt++) {
      motorAForward(unitIndex);
      delay(PUSHER_DURATION_MS);
      stopMotorA(unitIndex);

      if (waitForBillDetected(unitIndex, IR_DETECT_TIMEOUT_MS)) {
        detected = true;
        break;
      }
    }

    if (!detected) {
      stopMotorA(unitIndex);
      stopMotorB(unitIndex);
      *errorCode = "JAM";
      return dispensed;
    }

    delay(ROLLER_EXTRA_MS);
    dispensed++;

    if (!waitForBillCleared(unitIndex, BILL_CLEAR_TIMEOUT_MS)) {
      stopMotorA(unitIndex);
      stopMotorB(unitIndex);
      *errorCode = "JAM";
      return dispensed;
    }

    if (i < count - 1) {
      delay(INTER_BILL_DELAY_MS);
    }
  }

  stopMotorA(unitIndex);
  stopMotorB(unitIndex);
  return dispensed;
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
  stopAllDispensers();
  sorter.stop();
  sorter.setCurrentPosition(0);
  sorterHomed = false;
  sorterHomeFailed = false;
  currentSlot = 0;
  digitalWrite(ENABLE_PIN, HIGH);

  StaticJsonDocument<64> doc;
  doc["status"] = "OK";
  sendDocument(doc);
}

void handleHome() {
  if (!homeSorter()) {
    sendError("TIMEOUT");
    return;
  }
  StaticJsonDocument<96> doc;
  doc["status"] = "OK";
  doc["position"] = 0;
  sendDocument(doc);
}

void handleSort(JsonDocument &cmdDoc) {
  const char *denom = cmdDoc["denom"] | "";
  const int slot = slotForDenom(denom);
  if (slot < 1) {
    sendError("INVALID_DENOM");
    return;
  }
  if (!sorterHomed) {
    sendError("NOT_HOMED");
    return;
  }
  if (!moveSorterToSlot((uint8_t)slot)) {
    sendError("TIMEOUT");
    return;
  }

  StaticJsonDocument<96> doc;
  doc["status"] = "READY";
  doc["slot"] = slot;
  sendDocument(doc);
}

void handleSortStatus() {
  StaticJsonDocument<160> doc;
  doc["status"] = "OK";
  doc["position"] = sorter.currentPosition();
  doc["slot"] = currentSlot;
  doc["homed"] = sorterHomed;
  sendDocument(doc);
}

void handleDispense(JsonDocument &cmdDoc) {
  const char *denom = cmdDoc["denom"] | "";
  const int count = cmdDoc["count"] | 0;
  const int unitIndex = findDispenserIndex(denom);
  if (unitIndex < 0) {
    sendError("INVALID_DENOM");
    return;
  }
  if (count < 1 || count > 20) {
    sendError("INVALID_COUNT");
    return;
  }

  const char *errorCode = nullptr;
  const int dispensed = dispenseBills((uint8_t)unitIndex, count, &errorCode);
  if (errorCode != nullptr) {
    sendError(errorCode, dispensed);
    return;
  }

  StaticJsonDocument<96> doc;
  doc["status"] = "OK";
  doc["dispensed"] = dispensed;
  sendDocument(doc);
}

void handleDispenseStatus(JsonDocument &cmdDoc) {
  const char *denom = cmdDoc["denom"] | "";
  if (findDispenserIndex(denom) < 0) {
    sendError("INVALID_DENOM");
    return;
  }

  StaticJsonDocument<96> doc;
  doc["status"] = "OK";
  doc["ready"] = true;
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
  } else if (strcmp(cmd, "HOME") == 0) {
    handleHome();
  } else if (strcmp(cmd, "SORT") == 0) {
    handleSort(cmdDoc);
  } else if (strcmp(cmd, "SORT_STATUS") == 0) {
    handleSortStatus();
  } else if (strcmp(cmd, "DISPENSE") == 0) {
    handleDispense(cmdDoc);
  } else if (strcmp(cmd, "DISPENSE_STATUS") == 0) {
    handleDispenseStatus(cmdDoc);
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

void setupStepper() {
  pinMode(STEP_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);
  pinMode(ENABLE_PIN, OUTPUT);
  pinMode(LIMIT_PIN, INPUT_PULLUP);
  digitalWrite(ENABLE_PIN, HIGH);
  sorter.setMaxSpeed(SORT_MAX_SPEED);
  sorter.setAcceleration(SORT_ACCELERATION);
}

void setupDispensers() {
  for (uint8_t i = 0; i < DISPENSER_COUNT; i++) {
    pinMode(dispensers[i].motorAIn1, OUTPUT);
    pinMode(dispensers[i].motorAIn2, OUTPUT);
    pinMode(dispensers[i].motorBIn3, OUTPUT);
    if (dispensers[i].motorBIn4 != NO_PIN) {
      pinMode(dispensers[i].motorBIn4, OUTPUT);
    }
    pinMode(dispensers[i].irSensorPin, INPUT_PULLUP);
  }
  stopAllDispensers();
}

void setup() {
  Serial.begin(115200);
  inputLine.reserve(256);
  setupStepper();
  setupDispensers();
  delay(250);
  sendReadyEvent();
  homeSorter();
}

void loop() {
  handleSerialInput();
}
