#include <Arduino.h>
#include <ArduinoJson.h>
#include <AccelStepper.h>

// Coinnect Mega #1 firmware: bill sorting + bill dispensing.
// Serial protocol: newline-delimited JSON at 115200 baud.

static const char *FIRMWARE_VERSION = "2.0.0";
static const char *CONTROLLER_ID = "BILL";

// Stepper / A4988 pins.
static const uint8_t STEP_PIN = 6;
static const uint8_t DIR_PIN = 7;
static const uint8_t ENABLE_PIN = 4;
static const uint8_t LIMIT_PIN = 5;

// Conveyor motor pins (IN1-IN4 of single L298N driver controlling both conveyors)
static const uint8_t CONVEYOR_PHP_IN1 = 2;
static const uint8_t CONVEYOR_PHP_IN2 = 3;
static const uint8_t CONVEYOR_FOREIGN_IN1 = 8;
static const uint8_t CONVEYOR_FOREIGN_IN2 = 9;

// Configurable conveyor run duration (in milliseconds)
static const unsigned long CONVEYOR_DURATION_MS = 3000;

// A4988 enable is active LOW. Negative speed is the documented home direction.
static const long HOME_SPEED_STEPS_PER_SEC = -7500;
static const long HOME_BACKOFF_STEPS = 800;
static const unsigned long HOME_TIMEOUT_MS = 60000;
static const unsigned long SORT_TIMEOUT_MS = 60000;
static const float SORT_MAX_SPEED = 12000.0;
static const float SORT_ACCELERATION = 30000.0;
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
    {10, 11, 12, 13, A0, "PHP_20"},
    {14, 15, 16, 17, A1, "PHP_50"},
    {18, 19, 20, 21, A2, "PHP_100"},
    {22, 23, 24, 25, A3, "PHP_200"},
    {26, 27, 28, 29, A4, "PHP_500"},
    {30, 31, 32, 33, A5, "PHP_1000"},
    {34, 35, 36, 37, A6, "USD_10"},
    {38, 39, 40, 41, A7, "USD_50"},
    {42, 43, 44, 45, A8, "EUR_5"},
    {46, 47, 48, 49, A9, "EUR_10"}
};

static const uint8_t DISPENSER_COUNT = sizeof(dispensers) / sizeof(dispensers[0]);

struct SortSlotMap {
  const char *denom;
  uint8_t slot;
};

static const SortSlotMap sortSlotMap[] = {
    {"PHP_20", 1},   {"PHP_50", 2},   {"PHP_100", 3},
    {"PHP_200", 4},  {"PHP_500", 5},  {"PHP_1000", 6},
    {"USD_10", 7},   {"USD_50", 7},
    {"EUR_5", 8},    {"EUR_10", 8},
};

static const long SLOT_POSITIONS[] = {
    0, 30000, 60000, 90000, 122500, 153500, 187500, 219500,
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
  // Require multiple consecutive LOW reads to filter EMI noise
  const uint8_t DEBOUNCE_COUNT = 5;
  for (uint8_t i = 0; i < DEBOUNCE_COUNT; i++) {
    if (digitalRead(LIMIT_PIN) != LOW) {
      return false;
    }
    delayMicroseconds(1000); // 1ms between reads
  }
  return true;
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
  const long currentPos = sorter.currentPosition();
  const long steps = targetPosition - currentPos;

  if (steps == 0) {
    currentSlot = slot;
    return true;
  }

  enableStepper();
  float speed = (steps > 0) ? SORT_MAX_SPEED : -SORT_MAX_SPEED;
  sorter.setMaxSpeed(SORT_MAX_SPEED);
  sorter.setSpeed(speed);

  const unsigned long startedAt = millis();
  while ((steps > 0 && sorter.currentPosition() < targetPosition) ||
         (steps < 0 && sorter.currentPosition() > targetPosition)) {
    sorter.runSpeed();
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

void runConveyorForDenom(const char *denom) {
  bool isPhp = (strncmp(denom, "PHP_", 4) == 0);
  if (isPhp) {
    digitalWrite(CONVEYOR_PHP_IN1, HIGH);
    digitalWrite(CONVEYOR_PHP_IN2, LOW);
    delay(CONVEYOR_DURATION_MS);
    digitalWrite(CONVEYOR_PHP_IN1, LOW);
    digitalWrite(CONVEYOR_PHP_IN2, LOW);
  } else {
    digitalWrite(CONVEYOR_FOREIGN_IN1, HIGH);
    digitalWrite(CONVEYOR_FOREIGN_IN2, LOW);
    delay(CONVEYOR_DURATION_MS);
    digitalWrite(CONVEYOR_FOREIGN_IN1, LOW);
    digitalWrite(CONVEYOR_FOREIGN_IN2, LOW);
  }
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
  
  if (dispensed > 0) {
    runConveyorForDenom(denom);
  }

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

void handleConveyor(JsonDocument &cmdDoc) {
  const char *target = cmdDoc["target"] | "";
  if (strcmp(target, "PHP") == 0) {
    digitalWrite(CONVEYOR_PHP_IN1, HIGH);
    digitalWrite(CONVEYOR_PHP_IN2, LOW);
    delay(1000); // Test for 1 second
    digitalWrite(CONVEYOR_PHP_IN1, LOW);
    digitalWrite(CONVEYOR_PHP_IN2, LOW);

    StaticJsonDocument<96> doc;
    doc["status"] = "OK";
    doc["target"] = "PHP";
    sendDocument(doc);
  } else if (strcmp(target, "FOREIGN") == 0) {
    digitalWrite(CONVEYOR_FOREIGN_IN1, HIGH);
    digitalWrite(CONVEYOR_FOREIGN_IN2, LOW);
    delay(1000); // Test for 1 second
    digitalWrite(CONVEYOR_FOREIGN_IN1, LOW);
    digitalWrite(CONVEYOR_FOREIGN_IN2, LOW);

    StaticJsonDocument<96> doc;
    doc["status"] = "OK";
    doc["target"] = "FOREIGN";
    sendDocument(doc);
  } else {
    sendError("INVALID_PARAM");
  }
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
  } else if (strcmp(cmd, "CONVEYOR") == 0) {
    handleConveyor(cmdDoc);
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

void setupConveyors() {
  pinMode(CONVEYOR_PHP_IN1, OUTPUT);
  pinMode(CONVEYOR_PHP_IN2, OUTPUT);
  pinMode(CONVEYOR_FOREIGN_IN1, OUTPUT);
  pinMode(CONVEYOR_FOREIGN_IN2, OUTPUT);

  digitalWrite(CONVEYOR_PHP_IN1, LOW);
  digitalWrite(CONVEYOR_PHP_IN2, LOW);
  digitalWrite(CONVEYOR_FOREIGN_IN1, LOW);
  digitalWrite(CONVEYOR_FOREIGN_IN2, LOW);
}

void setup() {
  Serial.begin(115200);
  inputLine.reserve(256);
  setupStepper();
  setupDispensers();
  setupConveyors();
  delay(250);
  sendReadyEvent();
  // NOTE: homeSorter() removed from setup() to avoid blocking serial
  // command processing for up to 12s. The backend should send a HOME
  // command after confirming the connection with VERSION/PING.
}

void loop() {
  handleSerialInput();
}
