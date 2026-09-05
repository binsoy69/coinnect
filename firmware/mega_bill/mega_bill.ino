#include <Arduino.h>
#include <ArduinoJson.h>
#include <AccelStepper.h>
#include <EEPROM.h>

// Coinnect Mega #1 firmware: bill sorting + bill dispensing.
// Serial protocol: newline-delimited JSON at 115200 baud.

static const char *FIRMWARE_VERSION = "3.0.0";
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

static long SLOT_POSITIONS[] = {
    0, 30000, 60000, 90000, 122500, 153500, 187500, 219500,
};

AccelStepper sorter(AccelStepper::DRIVER, STEP_PIN, DIR_PIN);

static String inputLine;
static bool sorterHomed = false;
static bool sorterHomeFailed = false;
static int currentSlot = 0;
static unsigned long conveyorStopTimePhp = 0;
static unsigned long conveyorStopTimeForeign = 0;
static bool conveyorPhpActive = false;
static bool conveyorForeignActive = false;

static long currentCommandId = -1;

// Non-blocking bill dispensing state variables
static bool dispenseActive = false;
static uint8_t dispenseUnitIndex = 0;
static int dispenseTargetCount = 0;
static int dispenseActualCount = 0;
static uint8_t dispenseAttempt = 0;
static long dispenseCommandId = -1;
static char dispenseOperationId[37] = "";

struct __attribute__((packed)) OperationJournalRecord {
  uint32_t magic;
  uint32_t sequence;
  char operationId[37];
  uint8_t state;  // 1=STARTED, 2=COMPLETED, 3=FAILED, 4=AMBIGUOUS
  int16_t dispensed;
  uint16_t crc;
};
static const uint32_t JOURNAL_MAGIC = 0x434E4A31UL;
static OperationJournalRecord journalRecord = {};
static int journalSlot = -1;

uint16_t journalCrc(const OperationJournalRecord &record) {
  const uint8_t *bytes = reinterpret_cast<const uint8_t *>(&record);
  uint16_t crc = 0xFFFF;
  for (size_t i = 0; i < sizeof(OperationJournalRecord) - sizeof(record.crc); i++) {
    crc ^= bytes[i];
    for (uint8_t bit = 0; bit < 8; bit++) crc = (crc & 1) ? (crc >> 1) ^ 0xA001 : crc >> 1;
  }
  return crc;
}

void loadOperationJournal() {
  bool corrupt = false;
  const int slots = EEPROM.length() / sizeof(OperationJournalRecord);
  for (int slot = 0; slot < slots; slot++) {
    OperationJournalRecord candidate;
    EEPROM.get(slot * sizeof(OperationJournalRecord), candidate);
    if (candidate.magic != JOURNAL_MAGIC) continue;
    if (candidate.crc != journalCrc(candidate)) { corrupt = true; continue; }
    if (journalSlot < 0 || candidate.sequence > journalRecord.sequence) {
      journalRecord = candidate;
      journalSlot = slot;
    }
  }
  if (corrupt) {
    journalRecord = {};
    journalRecord.state = 4;
  }
}

void persistOperation(uint8_t state, const char *operationId, int dispensed) {
  OperationJournalRecord next = {};
  next.magic = JOURNAL_MAGIC;
  next.sequence = journalRecord.sequence + 1;
  strncpy(next.operationId, operationId ? operationId : "", 36);
  next.operationId[36] = '\0';
  next.state = state;
  next.dispensed = dispensed;
  next.crc = journalCrc(next);
  const int slots = EEPROM.length() / sizeof(OperationJournalRecord);
  journalSlot = (journalSlot + 1) % slots;
  EEPROM.put(journalSlot * sizeof(OperationJournalRecord), next);
  journalRecord = next;
}

bool isValidOperationId(const char *value) {
  if (!value || strlen(value) != 36) return false;
  for (uint8_t i = 0; i < 36; i++) {
    if (i == 8 || i == 13 || i == 18 || i == 23) {
      if (value[i] != '-') return false;
    } else if (!isxdigit(value[i])) return false;
  }
  return true;
}

bool findOperation(const char *operationId, OperationJournalRecord &found) {
  bool matched = false;
  const int slots = EEPROM.length() / sizeof(OperationJournalRecord);
  for (int slot = 0; slot < slots; slot++) {
    OperationJournalRecord candidate;
    EEPROM.get(slot * sizeof(OperationJournalRecord), candidate);
    if (candidate.magic == JOURNAL_MAGIC && candidate.crc == journalCrc(candidate)
        && strcmp(candidate.operationId, operationId) == 0
        && (!matched || candidate.sequence > found.sequence)) {
      found = candidate;
      matched = true;
    }
  }
  return matched;
}

void clearCorruptJournalSlots() {
  const int slots = EEPROM.length() / sizeof(OperationJournalRecord);
  for (int slot = 0; slot < slots; slot++) {
    OperationJournalRecord candidate;
    EEPROM.get(slot * sizeof(OperationJournalRecord), candidate);
    if (candidate.magic == JOURNAL_MAGIC && candidate.crc != journalCrc(candidate)) {
      uint32_t cleared = 0;
      EEPROM.put(slot * sizeof(OperationJournalRecord), cleared);
    }
  }
}

enum BillDispenseStep {
  BILL_STEP_IDLE,
  BILL_STEP_SPINUP,
  BILL_STEP_PUSHER_ON,
  BILL_STEP_PUSHER_OFF,
  BILL_STEP_ROLLER_EXTRA,
  BILL_STEP_WAIT_CLEAR,
  BILL_STEP_INTER_BILL
};
static BillDispenseStep billDispenseStep = BILL_STEP_IDLE;
static unsigned long billStepStartMs = 0;


void sendDocument(JsonDocument &doc) {
  if (currentCommandId >= 0) {
    doc["id"] = currentCommandId;
  }
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

void sendError(const char *code, int dispensed = -1, const char *operationId = NULL) {
  StaticJsonDocument<128> doc;
  doc["status"] = "ERROR";
  doc["code"] = code;
  if (dispensed >= 0) {
    doc["dispensed"] = dispensed;
  }
  if (operationId && operationId[0]) doc["operation_id"] = operationId;
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

enum SorterState {
  STATE_IDLE,
  STATE_HOMING_TO_LIMIT,
  STATE_HOMING_BACKOFF,
  STATE_SORTING_MOVE
};

static SorterState sorterState = STATE_IDLE;
static unsigned long sorterActionStartMs = 0;
static long sorterTargetPos = 0;
static long targetSlotAfterMove = 0;
static long asyncCommandId = -1;

void updateSorterStateMachine() {
  if (sorterState == STATE_IDLE) {
    return;
  }

  if (sorterState == STATE_HOMING_TO_LIMIT) {
    sorter.runSpeed();
    if (limitTriggered()) {
      sorter.stop();
      sorter.setCurrentPosition(0);
      sorter.moveTo(HOME_BACKOFF_STEPS);
      sorterState = STATE_HOMING_BACKOFF;
    } else if (millis() - sorterActionStartMs > HOME_TIMEOUT_MS) {
      sorter.stop();
      sorterHomed = false;
      sorterHomeFailed = true;
      currentSlot = 0;
      disableStepperIfAllowed();
      sorterState = STATE_IDLE;
      
      currentCommandId = asyncCommandId;
      sendError("TIMEOUT");
      currentCommandId = -1;
    }
  } 
  else if (sorterState == STATE_HOMING_BACKOFF) {
    sorter.run();
    if (sorter.distanceToGo() == 0) {
      sorter.setCurrentPosition(0);
      sorterHomed = true;
      sorterHomeFailed = false;
      currentSlot = 0;
      disableStepperIfAllowed();
      sorterState = STATE_IDLE;

      currentCommandId = asyncCommandId;
      StaticJsonDocument<96> doc;
      doc["status"] = "OK";
      doc["position"] = 0;
      sendDocument(doc);
      currentCommandId = -1;
    } else if (millis() - sorterActionStartMs > HOME_TIMEOUT_MS) {
      sorter.stop();
      sorterHomed = false;
      sorterHomeFailed = true;
      currentSlot = 0;
      disableStepperIfAllowed();
      sorterState = STATE_IDLE;

      currentCommandId = asyncCommandId;
      sendError("TIMEOUT");
      currentCommandId = -1;
    }
  } 
  else if (sorterState == STATE_SORTING_MOVE) {
    sorter.runSpeed();
    long currentPos = sorter.currentPosition();
    
    // Check if target is reached or passed
    bool reached = false;
    if (sorter.speed() > 0 && currentPos >= sorterTargetPos) {
      reached = true;
    } else if (sorter.speed() < 0 && currentPos <= sorterTargetPos) {
      reached = true;
    }

    if (reached) {
      sorter.stop();
      currentSlot = targetSlotAfterMove;
      disableStepperIfAllowed();
      sorterState = STATE_IDLE;

      currentCommandId = asyncCommandId;
      StaticJsonDocument<96> doc;
      doc["status"] = "READY";
      doc["slot"] = currentSlot;
      sendDocument(doc);
      currentCommandId = -1;
    } else if (millis() - sorterActionStartMs > SORT_TIMEOUT_MS) {
      sorter.stop();
      currentSlot = 0;
      disableStepperIfAllowed();
      sorterState = STATE_IDLE;

      currentCommandId = asyncCommandId;
      sendError("TIMEOUT");
      currentCommandId = -1;
    }
  }
}

void serviceDispense() {
  if (!dispenseActive) {
    return;
  }

  const unsigned long now = millis();

  switch (billDispenseStep) {
    case BILL_STEP_IDLE: {
      if (dispenseActualCount >= dispenseTargetCount) {
        stopMotorA(dispenseUnitIndex);
        stopMotorB(dispenseUnitIndex);
        dispenseActive = false;
        
        if (dispenseActualCount > 0) {
          runConveyorForDenom(dispensers[dispenseUnitIndex].denom);
        }

        persistOperation(2, dispenseOperationId, dispenseActualCount);
        currentCommandId = dispenseCommandId;
        StaticJsonDocument<160> doc;
        doc["status"] = "OK";
        doc["dispensed"] = dispenseActualCount;
        doc["operation_id"] = dispenseOperationId;
        sendDocument(doc);
        currentCommandId = -1;
        return;
      }

      if (dispenseActualCount == 0) {
        motorBForward(dispenseUnitIndex);
        billDispenseStep = BILL_STEP_SPINUP;
        billStepStartMs = now;
      } else {
        dispenseAttempt = 0;
        motorAForward(dispenseUnitIndex);
        billDispenseStep = BILL_STEP_PUSHER_ON;
        billStepStartMs = now;
      }
      break;
    }

    case BILL_STEP_SPINUP: {
      if (now - billStepStartMs >= ROLLER_SPINUP_MS) {
        dispenseAttempt = 0;
        motorAForward(dispenseUnitIndex);
        billDispenseStep = BILL_STEP_PUSHER_ON;
        billStepStartMs = now;
      }
      break;
    }

    case BILL_STEP_PUSHER_ON: {
      if (now - billStepStartMs >= PUSHER_DURATION_MS) {
        stopMotorA(dispenseUnitIndex);
        billDispenseStep = BILL_STEP_PUSHER_OFF;
        billStepStartMs = now;
      }
      break;
    }

    case BILL_STEP_PUSHER_OFF: {
      if (isBillDetected(dispenseUnitIndex)) {
        billDispenseStep = BILL_STEP_ROLLER_EXTRA;
        billStepStartMs = now;
      } else if (now - billStepStartMs >= IR_DETECT_TIMEOUT_MS) {
        dispenseAttempt++;
        if (dispenseAttempt < DISPENSE_RETRY_ATTEMPTS) {
          motorAForward(dispenseUnitIndex);
          billDispenseStep = BILL_STEP_PUSHER_ON;
          billStepStartMs = now;
        } else {
          // Retry failed - JAM
          stopMotorA(dispenseUnitIndex);
          stopMotorB(dispenseUnitIndex);
          dispenseActive = false;
          
          if (dispenseActualCount > 0) {
            runConveyorForDenom(dispensers[dispenseUnitIndex].denom);
          }
          persistOperation(3, dispenseOperationId, dispenseActualCount);
          currentCommandId = dispenseCommandId;
          sendError("JAM", dispenseActualCount, dispenseOperationId);
          currentCommandId = -1;
        }
      }
      break;
    }

    case BILL_STEP_ROLLER_EXTRA: {
      if (now - billStepStartMs >= ROLLER_EXTRA_MS) {
        dispenseActualCount++;
        billDispenseStep = BILL_STEP_WAIT_CLEAR;
        billStepStartMs = now;
      }
      break;
    }

    case BILL_STEP_WAIT_CLEAR: {
      if (!isBillDetected(dispenseUnitIndex)) {
        if (dispenseActualCount < dispenseTargetCount) {
          billDispenseStep = BILL_STEP_INTER_BILL;
          billStepStartMs = now;
        } else {
          billDispenseStep = BILL_STEP_IDLE; // Finish on next tick
        }
      } else if (now - billStepStartMs >= BILL_CLEAR_TIMEOUT_MS) {
        // Clear timed out - JAM
        stopMotorA(dispenseUnitIndex);
        stopMotorB(dispenseUnitIndex);
        dispenseActive = false;
        
        if (dispenseActualCount > 0) {
          runConveyorForDenom(dispensers[dispenseUnitIndex].denom);
        }
        persistOperation(3, dispenseOperationId, dispenseActualCount);
        currentCommandId = dispenseCommandId;
        sendError("JAM", dispenseActualCount, dispenseOperationId);
        currentCommandId = -1;
      }
      break;
    }

    case BILL_STEP_INTER_BILL: {
      if (now - billStepStartMs >= INTER_BILL_DELAY_MS) {
        dispenseAttempt = 0;
        motorAForward(dispenseUnitIndex);
        billDispenseStep = BILL_STEP_PUSHER_ON;
        billStepStartMs = now;
      }
      break;
    }
  }
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
  if (dispenseActive) persistOperation(4, dispenseOperationId, dispenseActualCount);
  dispenseActive = false; // Abort any active bill dispense
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

static bool emergencyLatched = false;

void handleEmergencyStop() {
  emergencyLatched = true;
  stopAllDispensers();
  if (dispenseActive && dispenseOperationId[0] != '\0') {
    persistOperation(4, dispenseOperationId, dispenseActualCount);
  }
  dispenseActive = false;
  billDispenseStep = BILL_STEP_IDLE;

  sorter.stop();
  sorterHomed = false;
  sorterHomeFailed = false;
  digitalWrite(ENABLE_PIN, HIGH);

  digitalWrite(CONVEYOR_PHP_IN1, LOW);
  digitalWrite(CONVEYOR_PHP_IN2, LOW);
  digitalWrite(CONVEYOR_FOREIGN_IN1, LOW);
  digitalWrite(CONVEYOR_FOREIGN_IN2, LOW);
  conveyorPhpActive = false;
  conveyorForeignActive = false;

  StaticJsonDocument<64> doc;
  doc["status"] = "OK";
  doc["stopped"] = true;
  sendDocument(doc);
}

void handleHome() {
  sorterHomeFailed = false;
  enableStepper();
  sorter.setMaxSpeed(abs(HOME_SPEED_STEPS_PER_SEC));
  sorter.setAcceleration(SORT_ACCELERATION);
  sorter.setSpeed(HOME_SPEED_STEPS_PER_SEC);

  sorterState = STATE_HOMING_TO_LIMIT;
  sorterActionStartMs = millis();
  asyncCommandId = currentCommandId;
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

  const long targetPosition = SLOT_POSITIONS[slot - 1];
  const long currentPos = sorter.currentPosition();
  const long steps = targetPosition - currentPos;

  if (steps == 0) {
    currentSlot = slot;
    StaticJsonDocument<96> doc;
    doc["status"] = "READY";
    doc["slot"] = slot;
    sendDocument(doc);
    return;
  }

  enableStepper();
  float speed = (steps > 0) ? SORT_MAX_SPEED : -SORT_MAX_SPEED;
  sorter.setMaxSpeed(SORT_MAX_SPEED);
  sorter.setSpeed(speed);

  sorterState = STATE_SORTING_MOVE;
  sorterActionStartMs = millis();
  sorterTargetPos = targetPosition;
  targetSlotAfterMove = slot;
  asyncCommandId = currentCommandId;
}

void handleSetSlotPositions(JsonDocument &cmdDoc) {
  JsonArray positions = cmdDoc["positions"];
  if (positions.isNull() || positions.size() != 8) {
    sendError("INVALID_PARAM");
    return;
  }

  for (size_t i = 0; i < 8; i++) {
    SLOT_POSITIONS[i] = positions[i];
  }

  StaticJsonDocument<64> doc;
  doc["status"] = "OK";
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
    conveyorStopTimePhp = millis() + CONVEYOR_DURATION_MS;
    conveyorPhpActive = true;
  } else {
    digitalWrite(CONVEYOR_FOREIGN_IN1, HIGH);
    digitalWrite(CONVEYOR_FOREIGN_IN2, LOW);
    conveyorStopTimeForeign = millis() + CONVEYOR_DURATION_MS;
    conveyorForeignActive = true;
  }
}

void handleDispense(JsonDocument &cmdDoc) {
  if (dispenseActive) {
    sendError("BUSY");
    return;
  }
  const char *denom = cmdDoc["denom"] | "";
  const int count = cmdDoc["count"] | 0;
  const char *operationId = cmdDoc["operation_id"] | "";
  if (!isValidOperationId(operationId)) {
    sendError("INVALID_PARAM", -1, operationId);
    return;
  }
  OperationJournalRecord prior = {};
  if (findOperation(operationId, prior)) {
    if (prior.state == 2) {
      StaticJsonDocument<160> doc;
      doc["status"] = "OK";
      doc["dispensed"] = prior.dispensed;
      doc["operation_id"] = operationId;
      sendDocument(doc);
    } else {
      sendError("RECOVERY_REQUIRED", prior.dispensed, operationId);
    }
    return;
  }
  if (journalRecord.state == 1 || journalRecord.state == 4) {
    sendError("RECOVERY_REQUIRED", journalRecord.dispensed, operationId);
    return;
  }
  const int unitIndex = findDispenserIndex(denom);
  if (unitIndex < 0) {
    sendError("INVALID_DENOM");
    return;
  }
  if (count < 1 || count > 20) {
    sendError("INVALID_COUNT");
    return;
  }

  persistOperation(1, operationId, 0);
  strncpy(dispenseOperationId, operationId, 36);
  dispenseOperationId[36] = '\0';
  dispenseCommandId = currentCommandId;
  dispenseActive = true;
  dispenseUnitIndex = (uint8_t)unitIndex;
  dispenseTargetCount = count;
  dispenseActualCount = 0;
  billDispenseStep = BILL_STEP_IDLE;
}

void handleOperationStatus(JsonDocument &cmdDoc) {
  const char *operationId = cmdDoc["operation_id"] | "";
  StaticJsonDocument<192> doc;
  doc["status"] = "OK";
  doc["operation_id"] = operationId;
  OperationJournalRecord prior = {};
  if (journalRecord.state == 4 && journalRecord.operationId[0] == '\0') {
    doc["operation_status"] = "AMBIGUOUS";
  } else if (!findOperation(operationId, prior)) {
    doc["operation_status"] = "NOT_FOUND";
  } else {
    doc["operation_status"] = prior.state == 1 ? "STARTED" : prior.state == 2 ? "COMPLETED" : prior.state == 3 ? "FAILED" : "AMBIGUOUS";
    doc["dispensed"] = prior.dispensed;
  }
  sendDocument(doc);
}

void handleOperationAck(JsonDocument &cmdDoc) {
  const char *operationId = cmdDoc["operation_id"] | "";
  if (journalRecord.state != 4 && strcmp(operationId, journalRecord.operationId) != 0) {
    sendError("NOT_FOUND", -1, operationId);
    return;
  }
  clearCorruptJournalSlots();
  persistOperation(0, "", 0);
  StaticJsonDocument<128> doc;
  doc["status"] = "OK";
  doc["operation_id"] = operationId;
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
    currentCommandId = -1;
    sendError("PARSE_ERROR");
    return;
  }

  currentCommandId = cmdDoc["id"] | -1;

  const char *cmd = cmdDoc["cmd"] | "";

  if (strcmp(cmd, "CAPABILITIES") == 0) {
    StaticJsonDocument<96> response;
    response["status"] = "OK";
    response["converter_protocol"] = 2;
    sendDocument(response);
    currentCommandId = -1;
    return;
  }
  // EMERGENCY_STOP & RESET commands should always override and stop any active motion immediately
  if (strcmp(cmd, "EMERGENCY_STOP") == 0) {
    sorterState = STATE_IDLE;
    asyncCommandId = -1;
    handleEmergencyStop();
    currentCommandId = -1;
    return;
  }
  if (strcmp(cmd, "RESET") == 0) {
    sorterState = STATE_IDLE;
    asyncCommandId = -1;
    handleReset();
    currentCommandId = -1;
    return;
  }

  if (strcmp(cmd, "EMERGENCY_CLEAR") == 0) {
    emergencyLatched = false;
    StaticJsonDocument<64> response;
    response["status"] = "OK";
    sendDocument(response);
    currentCommandId = -1;
    return;
  }
  if (emergencyLatched &&
      (strcmp(cmd, "DISPENSE") == 0 || strcmp(cmd, "SORT") == 0 ||
       strcmp(cmd, "HOME") == 0 || strcmp(cmd, "CONVEYOR") == 0)) {
    sendError("LOCKED_OUT");
    currentCommandId = -1;
    return;
  }

  // If stepper is currently moving, only allow instant non-modifying queries
  if (sorterState != STATE_IDLE) {
    if (strcmp(cmd, "PING") == 0) {
      handlePing();
    } else if (strcmp(cmd, "VERSION") == 0) {
      handleVersion();
    } else if (strcmp(cmd, "SORT_STATUS") == 0) {
      handleSortStatus();
    } else {
      sendError("LOCKED_OUT");
    }
    currentCommandId = -1;
    return;
  }

  if (strcmp(cmd, "PING") == 0) {
    handlePing();
  } else if (strcmp(cmd, "VERSION") == 0) {
    handleVersion();
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
  } else if (strcmp(cmd, "DISPENSE_OPERATION_STATUS") == 0) {
    handleOperationStatus(cmdDoc);
  } else if (strcmp(cmd, "DISPENSE_OPERATION_ACK") == 0) {
    handleOperationAck(cmdDoc);
  } else if (strcmp(cmd, "CONVEYOR") == 0) {
    handleConveyor(cmdDoc);
  } else if (strcmp(cmd, "SET_SLOT_POSITIONS") == 0) {
    handleSetSlotPositions(cmdDoc);
  } else {
    sendError("UNKNOWN_CMD");
  }

  // If the command did not initiate an async state transition, reset command ID
  if (sorterState == STATE_IDLE) {
    currentCommandId = -1;
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
  loadOperationJournal();
  delay(250);
  sendReadyEvent();
  // NOTE: homeSorter() removed from setup() to avoid blocking serial
  // command processing for up to 12s. The backend should send a HOME
  // command after confirming the connection with VERSION/PING.
}

void loop() {
  handleSerialInput();
  updateSorterStateMachine();
  serviceDispense();

  if (conveyorPhpActive && millis() >= conveyorStopTimePhp) {
    digitalWrite(CONVEYOR_PHP_IN1, LOW);
    digitalWrite(CONVEYOR_PHP_IN2, LOW);
    conveyorPhpActive = false;
  }
  if (conveyorForeignActive && millis() >= conveyorStopTimeForeign) {
    digitalWrite(CONVEYOR_FOREIGN_IN1, LOW);
    digitalWrite(CONVEYOR_FOREIGN_IN2, LOW);
    conveyorForeignActive = false;
  }
}
