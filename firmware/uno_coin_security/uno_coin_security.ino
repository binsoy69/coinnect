#include <Arduino.h>
#include <ArduinoJson.h>
#include <Servo.h>
#include <SPI.h>
#include <MFRC522.h>
#include <PinChangeInterrupt.h>
#include <EEPROM.h>

// ArduinoJson 7 allocates its document storage from the heap in 1 KB blocks.
// The Uno has only 2 KB of SRAM and this sketch keeps a command document and
// response document alive at the same time, so v7 can emit empty `{}` replies
// when the heap is exhausted. ArduinoJson 6 uses the fixed stack capacities
// declared below and is required for this AVR target.
#if ARDUINOJSON_VERSION_MAJOR >= 7
#error "uno_coin_security requires ArduinoJson 6.x (install ArduinoJson@6.21.6)"
#endif

// Coinnect Uno firmware: coin accept/dispense + security + RFID.
// Serial protocol: newline-delimited JSON at 115200 baud.

static const char *FIRMWARE_VERSION = "3.0.6-uno";
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

// The largest supported command is 122 bytes including its newline. A
// 128-byte buffer preserves bounded headroom without wasting scarce Uno SRAM.
static const size_t SERIAL_INPUT_CAPACITY = 128;
// Five request/response fields plus the transport-level command ID.
static const size_t COMMAND_JSON_CAPACITY = JSON_OBJECT_SIZE(6) + 64;
static char inputLine[SERIAL_INPUT_CAPACITY];
static size_t inputLength = 0;
static bool inputOverflow = false;
static unsigned long lastSerialActivityMs = 0;
static unsigned long lastRfidPollMs = 0;
static const unsigned long SERIAL_ACTIVITY_GUARD_MS = 100;
static const unsigned long RFID_POLL_INTERVAL_MS = 50;
static bool doorLocked = true;
static bool tamperLatched = false;
static bool securityArmed = false; // Starts disarmed/not listening on boot
static volatile bool coinAcceptorEnabled = false;
static const char *coinSorterPosition = "CENTER";
static int coinSessionTotal = 0;

enum CoinSessionState {
  COIN_SESSION_IDLE = 0,
  COIN_SESSION_ACTIVE = 1,
  COIN_SESSION_CLOSING = 2,
  COIN_SESSION_CLOSED = 3,
  COIN_SESSION_UNCERTAIN = 4
};

static CoinSessionState coinSessionState = COIN_SESSION_IDLE;
static uint32_t currentSessionId = 0;
static uint16_t sessionSequence = 0;
static uint16_t sessionCount1 = 0;
static uint16_t sessionCount5 = 0;
static uint16_t sessionCount10 = 0;
static uint16_t sessionCount20 = 0;

static unsigned long sessionDrainStartMs = 0;
static unsigned long sessionLastPulseMs = 0;
static unsigned long COIN_SESSION_MIN_DRAIN_MS = 500;
static unsigned long COIN_SESSION_QUIET_MS = 150;
static unsigned long COIN_SESSION_MAX_DRAIN_MS = 3000;

static volatile uint8_t coinPulseCount = 0;
static volatile unsigned long lastCoinPulseMs = 0;
static volatile unsigned long lastCoinInterruptMs = 0;

static volatile bool shockAFlag = false;
static volatile bool shockBFlag = false;
static volatile unsigned long lastShockAMs = 0;
static volatile unsigned long lastShockBMs = 0;

// Tamper indication must never block the serial or dispense state machines.
static bool tamperBlinkActive = false;
static uint8_t tamperBlinkTransitions = 0;
static unsigned long tamperBlinkLastMs = 0;
static const uint8_t TAMPER_BLINK_TRANSITIONS = 12;
static const unsigned long TAMPER_BLINK_INTERVAL_MS = 80;

// Non-blocking sorter and acceptance state variables
static bool sorterMoving = false;
static unsigned long sorterMoveStartMs = 0;
static bool coinHoldActive = false;
static unsigned long coinHoldStartMs = 0;
static bool coinAcceptorShouldBeEnabled = false;

// Non-blocking coin dispensing state variables
static bool dispenseActive = false;
static int dispenseDenom = 0;
static int dispenseTargetCount = 0;
static int dispenseActualCount = 0;
static int8_t dispenseDispenserIndex = 0;

enum DispenseStep {
  DISPENSE_STEP_IDLE,
  DISPENSE_STEP_SWEEP_OUT,
  DISPENSE_STEP_SWEEP_IN,
  DISPENSE_STEP_SETTLE
};
static DispenseStep dispenseStep = DISPENSE_STEP_IDLE;
static unsigned long dispenseStepStartMs = 0;
static const char *dispenseCommandContext = "DISPENSE";
static long dispenseCommandId = -1;
static char dispenseOperationId[37] = "";

// Checksummed, wear-levelled dispense journal. State values are
// 0=ACKNOWLEDGED, 1=STARTED, 2=COMPLETED, 3=FAILED, 4=AMBIGUOUS.
struct __attribute__((packed)) OperationJournalRecord {
  uint32_t magic;
  uint32_t sequence;
  char operationId[37];
  uint8_t state;
  int16_t dispensed;
  uint16_t crc;
};
static const uint32_t JOURNAL_MAGIC = 0x434E4A32UL;
static OperationJournalRecord journalRecord = {};
static int journalSlot = -1;

uint16_t journalCrc(const OperationJournalRecord &record) {
  const uint8_t *bytes = reinterpret_cast<const uint8_t *>(&record);
  uint16_t crc = 0xFFFF;
  for (size_t i = 0; i < sizeof(OperationJournalRecord) - sizeof(record.crc); i++) {
    crc ^= bytes[i];
    for (uint8_t bit = 0; bit < 8; bit++) {
      crc = (crc & 1) ? (crc >> 1) ^ 0xA001 : crc >> 1;
    }
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
    if (candidate.crc != journalCrc(candidate)) {
      corrupt = true;
      continue;
    }
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
    } else if (!isxdigit(value[i])) {
      return false;
    }
  }
  return true;
}

bool findOperation(const char *operationId, uint8_t &state, int16_t &dispensed) {
  bool matched = false;
  uint32_t latestSequence = 0;
  const int slots = EEPROM.length() / sizeof(OperationJournalRecord);
  for (int slot = 0; slot < slots; slot++) {
    OperationJournalRecord candidate;
    EEPROM.get(slot * sizeof(OperationJournalRecord), candidate);
    if (candidate.magic == JOURNAL_MAGIC &&
        candidate.crc == journalCrc(candidate) &&
        strcmp(candidate.operationId, operationId) == 0 &&
        (!matched || candidate.sequence > latestSequence)) {
      latestSequence = candidate.sequence;
      state = candidate.state;
      dispensed = candidate.dispensed;
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

static int changeC20 = 0;
static int changeC10 = 0;
static int changeC5 = 0;
static int changeC1 = 0;
static int changeState = 0; // 0=20, 1=10, 2=5, 3=1, 4=done


static long currentCommandId = -1;


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
  doc["reset_cause"] = MCUSR;
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

void sendCoinSessionPulseEvent(uint32_t sid, uint16_t seq, int denom, uint16_t count) {
  StaticJsonDocument<128> doc;
  doc["event"] = "COIN_SESSION_PULSE";
  doc["sid"] = sid;
  doc["seq"] = seq;
  doc["denom"] = denom;
  doc["count"] = count;
  sendDocument(doc);
}

void sendError(const char *code, int dispensed = -1, const char *operationId = NULL) {
  StaticJsonDocument<128> doc;
  doc["status"] = "ERROR";
  doc["code"] = code;
  if (dispensed >= 0) {
    doc["dispensed"] = dispensed;
  }
  if (operationId && operationId[0]) {
    doc["operation_id"] = operationId;
  }
  sendDocument(doc);
}

void sendCommandError(JsonDocument &doc, const char *code, int dispensed = -1,
                      const char *operationId = NULL) {
  doc.clear();
  doc["status"] = "ERROR";
  doc["code"] = code;
  if (dispensed >= 0) {
    doc["dispensed"] = dispensed;
  }
  if (operationId && operationId[0]) {
    doc["operation_id"] = operationId;
  }
  sendDocument(doc);
}

void sendCommandParseError(JsonDocument &doc, const char *detail,
                           size_t receivedBytes) {
  doc.clear();
  doc["status"] = "ERROR";
  doc["code"] = "PARSE_ERROR";
  doc["detail"] = detail;
  doc["received_bytes"] = receivedBytes;
  sendDocument(doc);
}

void sendParseError(const char *detail, size_t receivedBytes) {
  StaticJsonDocument<128> doc;
  doc["status"] = "ERROR";
  doc["code"] = "PARSE_ERROR";
  doc["detail"] = detail;
  doc["received_bytes"] = receivedBytes;
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
  if (!dispenser.servo->attached()) {
    dispenser.servo->attach(
        index == 0 ? SERVO_PHP_1_PIN :
        index == 1 ? SERVO_PHP_5_PIN :
        index == 2 ? SERVO_PHP_10_PIN : SERVO_PHP_20_PIN);
  }
  dispenser.servo->write(dispenser.pushToResetFirst ? SERVO_PUSH_DEG
                                                     : SERVO_RESET_DEG);
}

void attachCoinSorterIfNeeded() {
  if (!coinSorterServo.attached()) {
    coinSorterServo.attach(COIN_SORTER_SERVO_PIN);
  }
}

void attachDispenserIfNeeded(uint8_t index) {
  CoinDispenser &dispenser = coinDispensers[index];
  if (!dispenser.servo->attached()) {
    dispenser.servo->attach(
        index == 0 ? SERVO_PHP_1_PIN :
        index == 1 ? SERVO_PHP_5_PIN :
        index == 2 ? SERVO_PHP_10_PIN : SERVO_PHP_20_PIN);
  }
}

void detachActiveDispenser() {
  if (dispenseDispenserIndex >= 0 &&
      dispenseDispenserIndex < (int8_t)COIN_DISPENSER_COUNT) {
    coinDispensers[(uint8_t)dispenseDispenserIndex].servo->detach();
  }
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
  if (tamperLatched) return;
  if (strcmp(position, "LEFT") == 0) {
    coinSorterPosition = "LEFT";
  } else if (strcmp(position, "RIGHT") == 0) {
    coinSorterPosition = "RIGHT";
  } else {
    coinSorterPosition = "CENTER";
  }
  attachCoinSorterIfNeeded();
  coinSorterServo.write(sorterAngleForPosition(position));
  sorterMoving = true;
  sorterMoveStartMs = millis();
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
  if (!enabled && coinSessionState == COIN_SESSION_IDLE) {
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

void startTamperBlink() {
  tamperBlinkActive = true;
  tamperBlinkTransitions = 0;
  tamperBlinkLastMs = millis();
}

void serviceTamperBlink() {
  if (!tamperBlinkActive ||
      millis() - tamperBlinkLastMs < TAMPER_BLINK_INTERVAL_MS) {
    return;
  }

  tamperBlinkLastMs = millis();
  tamperBlinkTransitions++;
  digitalWrite(LED_RED_PIN, tamperBlinkTransitions % 2 ? LOW : HIGH);
  if (tamperBlinkTransitions >= TAMPER_BLINK_TRANSITIONS) {
    tamperBlinkActive = false;
    digitalWrite(LED_RED_PIN, HIGH);
  }
}

void handleTamper(const char *sensor) {
  if (tamperLatched) {
    return;
  }
  tamperLatched = true;
  coinAcceptorShouldBeEnabled = false;
  setCoinAcceptorEnabled(false);
  setCoinSorterPosition("CENTER");
  lockDoor(true);
  startTamperBlink();
  sendTamperEvent(sensor);
}

void coinPulseISR() {
  if (!coinAcceptorEnabled && coinSessionState != COIN_SESSION_CLOSING && coinSessionState != COIN_SESSION_ACTIVE) {
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

  if (tamperLatched) {
    return;
  }

  if (a) {
    handleTamper("A");
  }
  if (b && !tamperLatched) {
    handleTamper("B");
  }
}

void serviceSorter() {
  if (sorterMoving) {
    if (millis() - sorterMoveStartMs >= COIN_SORTER_SETTLE_MS) {
      sorterMoving = false;
      if (strcmp(coinSorterPosition, "CENTER") == 0) {
        if (coinAcceptorShouldBeEnabled && !tamperLatched) {
          setCoinAcceptorEnabled(true);
        }
      }
      coinSorterServo.detach();
    }
  }
}

void serviceCoinHold() {
  if (coinHoldActive && !sorterMoving) {
    if (millis() - coinHoldStartMs >= COIN_SORTER_HOLD_MS) {
      coinHoldActive = false;
      setCoinSorterPosition("CENTER");
    }
  }
}

void serviceCoinSessionDrain() {
  if (coinSessionState != COIN_SESSION_CLOSING) {
    return;
  }
  const unsigned long now = millis();
  const unsigned long elapsed = now - sessionDrainStartMs;
  const unsigned long sinceLastPulse = now - sessionLastPulseMs;

  noInterrupts();
  const bool inFlightPulses = (coinPulseCount > 0);
  interrupts();

  if (!inFlightPulses && elapsed >= COIN_SESSION_MIN_DRAIN_MS && sinceLastPulse >= COIN_SESSION_QUIET_MS) {
    coinSessionState = COIN_SESSION_CLOSED;
  } else if (elapsed >= COIN_SESSION_MAX_DRAIN_MS) {
    coinSessionState = COIN_SESSION_UNCERTAIN;
  }
}

void serviceCoinPulseTrain() {
  uint8_t pulses = 0;
  const unsigned long now = millis();

  if (!coinAcceptorEnabled && coinSessionState != COIN_SESSION_CLOSING && coinSessionState != COIN_SESSION_ACTIVE) {
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
    if (coinSessionState != COIN_SESSION_IDLE) {
      coinSessionState = COIN_SESSION_UNCERTAIN;
      coinAcceptorShouldBeEnabled = false;
      setCoinAcceptorEnabled(false);
    }
    return;
  }

  coinSessionTotal += denom;
  sessionLastPulseMs = now;
  
  // Disable acceptor physically during sorting
  coinAcceptorEnabled = false;
  digitalWrite(COIN_ACCEPTOR_ENABLE_PIN, LOW);
  if (coinSessionState == COIN_SESSION_IDLE) clearCoinPulseTrain();

  // Move sorter to denomination position non-blockingly
  const char *targetPos = sorterPositionForDenom(denom);
  if (!tamperLatched) setCoinSorterPosition(targetPos);

  if (coinSessionState == COIN_SESSION_ACTIVE || coinSessionState == COIN_SESSION_CLOSING) {
    sessionSequence++;
    uint16_t curCount = 0;
    if (denom == 1) { sessionCount1++; curCount = sessionCount1; }
    else if (denom == 5) { sessionCount5++; curCount = sessionCount5; }
    else if (denom == 10) { sessionCount10++; curCount = sessionCount10; }
    else if (denom == 20) { sessionCount20++; curCount = sessionCount20; }
    sendCoinSessionPulseEvent(currentSessionId, sessionSequence, denom, curCount);
  } else {
    sendCoinInEvent(denom);
  }

  coinHoldActive = true;
  coinHoldStartMs = now;
}

void serviceDispense() {
  if (!dispenseActive) {
    return;
  }

  if (tamperLatched) {
    if (strcmp(dispenseCommandContext, "DISPENSE") == 0) {
      persistOperation(4, dispenseOperationId, dispenseActualCount);
      currentCommandId = dispenseCommandId;
      sendError("AMBIGUOUS", dispenseActualCount, dispenseOperationId);
      currentCommandId = -1;
    } else {
      sendError("AMBIGUOUS", dispenseActualCount);
    }
    detachActiveDispenser();
    dispenseActive = false;
    return;
  }

  const unsigned long now = millis();

  switch (dispenseStep) {
    case DISPENSE_STEP_IDLE: {
      if (dispenseTargetCount == 0 || dispenseActualCount >= dispenseTargetCount) {
        if (strcmp(dispenseCommandContext, "CHANGE") == 0) {
          changeState++;
          int nextDenom = -1;
          int nextCount = 0;
          if (changeState == 1) { nextDenom = 10; nextCount = changeC10; }
          else if (changeState == 2) { nextDenom = 5; nextCount = changeC5; }
          else if (changeState == 3) { nextDenom = 1; nextCount = changeC1; }
          
          if (nextDenom != -1 && nextCount > 0) {
            detachActiveDispenser();
            dispenseDenom = nextDenom;
            dispenseTargetCount = nextCount;
            dispenseActualCount = 0;
            dispenseDispenserIndex = findCoinDispenser(nextDenom);
            if (dispenseDispenserIndex < 0) {
              sendError("INVALID_DENOM", dispenseActualCount);
              dispenseActive = false;
              return;
            }
            dispenseStep = DISPENSE_STEP_SWEEP_OUT;
            dispenseStepStartMs = now;
            CoinDispenser &disp = coinDispensers[dispenseDispenserIndex];
            attachDispenserIfNeeded(dispenseDispenserIndex);
            disp.servo->write(disp.pushToResetFirst ? SERVO_RESET_DEG : SERVO_PUSH_DEG);
          } else if (changeState >= 4 || nextDenom == -1) {
            StaticJsonDocument<160> doc;
            doc["status"] = "OK";
            JsonObject breakdown = doc.createNestedObject("breakdown");
            if (changeC20 > 0) breakdown["20"] = changeC20;
            if (changeC10 > 0) breakdown["10"] = changeC10;
            if (changeC5 > 0) breakdown["5"] = changeC5;
            if (changeC1 > 0) breakdown["1"] = changeC1;
            sendDocument(doc);
            detachActiveDispenser();
            dispenseActive = false;
          }
        } else {
          persistOperation(2, dispenseOperationId, dispenseActualCount);
          currentCommandId = dispenseCommandId;
          StaticJsonDocument<160> doc;
          doc["status"] = "OK";
          doc["dispensed"] = dispenseActualCount;
          doc["operation_id"] = dispenseOperationId;
          sendDocument(doc);
          currentCommandId = -1;
          detachActiveDispenser();
          dispenseActive = false;
        }
        return;
      }

      dispenseStep = DISPENSE_STEP_SWEEP_OUT;
      dispenseStepStartMs = now;
      CoinDispenser &disp = coinDispensers[dispenseDispenserIndex];
      attachDispenserIfNeeded(dispenseDispenserIndex);
      disp.servo->write(disp.pushToResetFirst ? SERVO_RESET_DEG : SERVO_PUSH_DEG);
      break;
    }

    case DISPENSE_STEP_SWEEP_OUT: {
      if (now - dispenseStepStartMs >= 250) {
        dispenseStep = DISPENSE_STEP_SWEEP_IN;
        dispenseStepStartMs = now;
        CoinDispenser &disp = coinDispensers[dispenseDispenserIndex];
        attachDispenserIfNeeded(dispenseDispenserIndex);
        disp.servo->write(disp.pushToResetFirst ? SERVO_PUSH_DEG : SERVO_RESET_DEG);
      }
      break;
    }

    case DISPENSE_STEP_SWEEP_IN: {
      if (now - dispenseStepStartMs >= 250) {
        dispenseStep = DISPENSE_STEP_SETTLE;
        dispenseStepStartMs = now;
      }
      break;
    }

    case DISPENSE_STEP_SETTLE: {
      if (now - dispenseStepStartMs >= SERVO_CYCLE_SETTLE_MS) {
        dispenseActualCount++;
        dispenseStep = DISPENSE_STEP_IDLE;
      }
      break;
    }
  }
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

void handlePing(JsonDocument &doc) {
  doc.clear();
  doc["status"] = "OK";
  doc["message"] = "PONG";
  sendDocument(doc);
}

void handleVersion(JsonDocument &doc) {
  doc.clear();
  doc["status"] = "OK";
  doc["version"] = FIRMWARE_VERSION;
  doc["controller"] = CONTROLLER_ID;
  sendDocument(doc);
}

void handleReset(JsonDocument &doc) {
  noInterrupts();
  coinPulseCount = 0;
  shockAFlag = false;
  shockBFlag = false;
  interrupts();

  coinSessionTotal = 0;
  tamperLatched = false;
  tamperBlinkActive = false;
  securityArmed = true; // Armed during initialization/reconciliation
  coinAcceptorShouldBeEnabled = false;
  setCoinAcceptorEnabled(false);
  setCoinSorterPosition("CENTER");
  lockDoor(true);

  if (dispenseActive && strcmp(dispenseCommandContext, "DISPENSE") == 0) {
    persistOperation(4, dispenseOperationId, dispenseActualCount);
  }
  detachActiveDispenser();
  dispenseActive = false; // Abort any active coin dispensing

  doc.clear();
  doc["status"] = "OK";
  sendDocument(doc);
}

void handleCoinDispense(JsonDocument &cmdDoc) {
  if (dispenseActive) {
    sendCommandError(cmdDoc, "BUSY");
    return;
  }
  const int denom = cmdDoc["denom"] | 0;
  const int count = cmdDoc["count"] | 0;
  const char *operationId = cmdDoc["operation_id"] | "";
  if (!isValidOperationId(operationId)) {
    sendCommandError(cmdDoc, "INVALID_PARAM", -1, operationId);
    return;
  }

  uint8_t priorState = 0;
  int16_t priorDispensed = 0;
  if (findOperation(operationId, priorState, priorDispensed)) {
    if (priorState == 2) {
      cmdDoc.remove("cmd");
      cmdDoc.remove("denom");
      cmdDoc.remove("count");
      cmdDoc["status"] = "OK";
      cmdDoc["dispensed"] = priorDispensed;
      sendDocument(cmdDoc);
    } else {
      sendCommandError(cmdDoc, "RECOVERY_REQUIRED", priorDispensed, operationId);
    }
    return;
  }
  if (journalRecord.state == 1 || journalRecord.state == 4) {
    sendCommandError(cmdDoc, "RECOVERY_REQUIRED", journalRecord.dispensed, operationId);
    return;
  }

  if (!isValidCoinDenom(denom)) {
    sendCommandError(cmdDoc, "INVALID_DENOM");
    return;
  }
  if (count < 1 || count > 50) {
    sendCommandError(cmdDoc, "INVALID_COUNT");
    return;
  }
  if (tamperLatched) {
    sendCommandError(cmdDoc, "LOCKED_OUT", 0);
    return;
  }

  dispenseDispenserIndex = findCoinDispenser(denom);
  if (dispenseDispenserIndex < 0) {
    sendCommandError(cmdDoc, "INVALID_DENOM");
    return;
  }

  persistOperation(1, operationId, 0);
  strncpy(dispenseOperationId, operationId, 36);
  dispenseOperationId[36] = '\0';
  dispenseCommandId = currentCommandId;
  dispenseActive = true;
  dispenseDenom = denom;
  dispenseTargetCount = count;
  dispenseActualCount = 0;
  dispenseCommandContext = "DISPENSE";
  dispenseStep = DISPENSE_STEP_IDLE;
}

void handleOperationStatus(JsonDocument &cmdDoc) {
  const char *operationId = cmdDoc["operation_id"] | "";
  if (!isValidOperationId(operationId)) {
    sendCommandError(cmdDoc, "INVALID_PARAM", -1, operationId);
    return;
  }

  uint8_t priorState = 0;
  int16_t priorDispensed = 0;
  const bool journalIsAmbiguous =
      journalRecord.state == 4 && journalRecord.operationId[0] == '\0';
  const bool operationFound =
      findOperation(operationId, priorState, priorDispensed);
  cmdDoc.remove("cmd");
  cmdDoc["status"] = "OK";
  if (journalIsAmbiguous) {
    cmdDoc["operation_status"] = "AMBIGUOUS";
  } else if (!operationFound) {
    cmdDoc["operation_status"] = "NOT_FOUND";
  } else {
    cmdDoc["operation_status"] =
        priorState == 1 ? "STARTED" :
        priorState == 2 ? "COMPLETED" :
        priorState == 3 ? "FAILED" : "AMBIGUOUS";
    cmdDoc["dispensed"] = priorDispensed;
  }
  sendDocument(cmdDoc);
}

void handleOperationAck(JsonDocument &cmdDoc) {
  const char *operationId = cmdDoc["operation_id"] | "";
  if (!isValidOperationId(operationId)) {
    sendCommandError(cmdDoc, "INVALID_PARAM", -1, operationId);
    return;
  }
  if (journalRecord.state != 4 && strcmp(operationId, journalRecord.operationId) != 0) {
    sendCommandError(cmdDoc, "NOT_FOUND", -1, operationId);
    return;
  }
  clearCorruptJournalSlots();
  persistOperation(0, "", 0);
  cmdDoc.remove("cmd");
  cmdDoc["status"] = "OK";
  sendDocument(cmdDoc);
}

void handleCoinChange(JsonDocument &cmdDoc) {
  if (dispenseActive) {
    sendCommandError(cmdDoc, "BUSY");
    return;
  }
  const int amount = cmdDoc["amount"] | 0;
  if (amount < 1) {
    sendCommandError(cmdDoc, "INVALID_COUNT");
    return;
  }
  if (tamperLatched) {
    sendCommandError(cmdDoc, "LOCKED_OUT", 0);
    return;
  }

  calculateCoinBreakdown(amount, changeC20, changeC10, changeC5, changeC1);

  dispenseActive = true;
  dispenseCommandContext = "CHANGE";
  changeState = 0; // Starts with PHP 20
  
  // Set up first denomination to dispense
  int firstDenom = 20;
  int firstCount = changeC20;
  
  if (firstCount == 0) {
    changeState = 1;
    firstDenom = 10;
    firstCount = changeC10;
  }
  if (firstCount == 0) {
    changeState = 2;
    firstDenom = 5;
    firstCount = changeC5;
  }
  if (firstCount == 0) {
    changeState = 3;
    firstDenom = 1;
    firstCount = changeC1;
  }

  if (firstCount > 0) {
    dispenseDenom = firstDenom;
    dispenseTargetCount = firstCount;
    dispenseActualCount = 0;
    dispenseDispenserIndex = findCoinDispenser(firstDenom);
    if (dispenseDispenserIndex < 0) {
      sendCommandError(cmdDoc, "INVALID_DENOM");
      detachActiveDispenser();
      dispenseActive = false;
      return;
    }
    dispenseStep = DISPENSE_STEP_IDLE;
  } else {
    // Nothing to dispense
    cmdDoc.clear();
    cmdDoc["status"] = "OK";
    cmdDoc.createNestedObject("breakdown");
    sendDocument(cmdDoc);
    dispenseActive = false;
  }
}

void handleEmergencyStop(JsonDocument &cmdDoc) {
  const bool wasDispensing = dispenseActive;
  tamperLatched = true;
  coinHoldActive = false;
  sorterMoving = false;
  detachActiveDispenser();
  dispenseActive = false;

  coinAcceptorShouldBeEnabled = false;
  setCoinAcceptorEnabled(false);
  coinSorterServo.detach();

  if (wasDispensing && dispenseOperationId[0] != '\0') {
    persistOperation(4, dispenseOperationId, dispenseActualCount);
  }

  if (coinSessionState == COIN_SESSION_ACTIVE) {
    coinSessionState = COIN_SESSION_CLOSING;
    sessionDrainStartMs = millis();
    sessionLastPulseMs = millis();
  }

  cmdDoc.clear();
  cmdDoc["status"] = "OK";
  cmdDoc["stopped"] = true;
  sendDocument(cmdDoc);
}

void handleCoinReset(JsonDocument &doc) {
  const int previousTotal = coinSessionTotal;
  coinSessionTotal = 0;
  coinSessionState = COIN_SESSION_IDLE;
  currentSessionId = 0;
  sessionSequence = 0;
  sessionCount1 = 0;
  sessionCount5 = 0;
  sessionCount10 = 0;
  sessionCount20 = 0;

  coinAcceptorShouldBeEnabled = false;
  setCoinAcceptorEnabled(false);
  setCoinSorterPosition("CENTER");

  dispenseActive = false; // Abort any active coin dispensing
  detachActiveDispenser();

  doc.clear();
  doc["status"] = "OK";
  doc["previous_total"] = previousTotal;
  sendDocument(doc);
}

void handleCoinSessionStart(JsonDocument &cmdDoc) {
  if (tamperLatched) {
    sendCommandError(cmdDoc, "LOCKED_OUT");
    return;
  }
  if (!cmdDoc.containsKey("sid")) {
    sendCommandError(cmdDoc, "INVALID_PARAM");
    return;
  }

  const unsigned long grace = cmdDoc["grace_ms"] | 500UL;
  const unsigned long timeout = cmdDoc["timeout_ms"] | 3000UL;
  const unsigned long quiet = cmdDoc["quiet_ms"] | 150UL;
  if (grace < 500 || timeout < grace || timeout > 10000 || quiet < 150 || quiet > timeout) {
    sendCommandError(cmdDoc, "INVALID_PARAM");
    return;
  }
  COIN_SESSION_MIN_DRAIN_MS = grace;
  COIN_SESSION_MAX_DRAIN_MS = timeout;
  COIN_SESSION_QUIET_MS = quiet;
  const uint32_t requestedSid = cmdDoc["sid"].as<uint32_t>();
  if (!requestedSid || requestedSid < currentSessionId ||
      (requestedSid != currentSessionId && coinSessionState != COIN_SESSION_IDLE && coinSessionState != COIN_SESSION_CLOSED)) {
    sendCommandError(cmdDoc, "LOCKED_OUT");
    return;
  }
  if (requestedSid == currentSessionId) {
    if (coinSessionState != COIN_SESSION_ACTIVE) {
      sendCommandError(cmdDoc, "LOCKED_OUT");
      return;
    }
    cmdDoc.clear();
    cmdDoc["status"] = "OK";
    cmdDoc["sid"] = currentSessionId;
    cmdDoc["session_state"] = "ACTIVE";
    sendDocument(cmdDoc);
    return;
  }
  currentSessionId = requestedSid;
  sessionSequence = 0;
  sessionCount1 = 0;
  sessionCount5 = 0;
  sessionCount10 = 0;
  sessionCount20 = 0;
  coinSessionTotal = 0;
  coinSessionState = COIN_SESSION_ACTIVE;

  coinAcceptorShouldBeEnabled = true;
  setCoinAcceptorEnabled(true);

  cmdDoc.clear();
  cmdDoc["status"] = "OK";
  cmdDoc["sid"] = currentSessionId;
  cmdDoc["session_state"] = "ACTIVE";
  sendDocument(cmdDoc);
}

void handleCoinSessionStop(JsonDocument &cmdDoc) {
  if (cmdDoc.containsKey("sid") && cmdDoc["sid"].as<uint32_t>() != currentSessionId) {
    sendCommandError(cmdDoc, "INVALID_PARAM");
    return;
  }

  coinAcceptorShouldBeEnabled = false;
  setCoinAcceptorEnabled(false);

  const unsigned long now = millis();
  if (coinSessionState == COIN_SESSION_ACTIVE) {
    sessionDrainStartMs = now;
    sessionLastPulseMs = now;
    coinSessionState = COIN_SESSION_CLOSING;
  }

  cmdDoc.clear();
  cmdDoc["status"] = "OK";
  cmdDoc["sid"] = currentSessionId;
  cmdDoc["session_state"] = (coinSessionState == COIN_SESSION_CLOSED) ? "CLOSED" : "CLOSING";
  sendDocument(cmdDoc);
}

void handleCoinSessionStatus(JsonDocument &cmdDoc) {
  const int denom = cmdDoc["denom"] | 0;
  if (!isValidCoinDenom(denom)) {
    sendCommandError(cmdDoc, "INVALID_DENOM");
    return;
  }
  const char *stateStr = "IDLE";
  if (coinSessionState == COIN_SESSION_ACTIVE) stateStr = "ACTIVE";
  else if (coinSessionState == COIN_SESSION_CLOSING) stateStr = "CLOSING";
  else if (coinSessionState == COIN_SESSION_CLOSED) stateStr = "CLOSED";
  else if (coinSessionState == COIN_SESSION_UNCERTAIN) stateStr = "UNCERTAIN";
  uint16_t count = denom == 1 ? sessionCount1 : denom == 5 ? sessionCount5 : denom == 10 ? sessionCount10 : sessionCount20;
  cmdDoc.clear();
  cmdDoc["status"] = "OK";
  cmdDoc["sid"] = currentSessionId;
  cmdDoc["session_state"] = stateStr;
  cmdDoc["denom"] = denom;
  cmdDoc["count"] = count;
  sendDocument(cmdDoc);
}

void handleCoinAcceptorEnable(JsonDocument &cmdDoc) {
  if (!cmdDoc["enabled"].is<bool>()) {
    sendCommandError(cmdDoc, "INVALID_PARAM");
    return;
  }

  const bool enabled = cmdDoc["enabled"];
  if (enabled && tamperLatched) {
    sendCommandError(cmdDoc, "LOCKED_OUT");
    return;
  }

  coinAcceptorShouldBeEnabled = enabled;
  setCoinAcceptorEnabled(enabled);

  // Preserve the parsed fields and add the response status in place. Avoiding
  // a clear/rebuild keeps strings linked to the input buffer and lowers stack
  // pressure while HardwareSerial is transmitting.
  cmdDoc.remove("cmd");
  cmdDoc["status"] = "OK";
  cmdDoc["enabled"] = (bool)coinAcceptorEnabled;
  sendDocument(cmdDoc);
}


void handleCoinStatus(JsonDocument &doc) {
  doc.clear();
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
    sendCommandError(cmdDoc, "INVALID_PARAM");
    return;
  }

  setCoinSorterPosition(position);

  cmdDoc.clear();
  cmdDoc["status"] = "OK";
  cmdDoc["sorter_position"] = coinSorterPosition;
  cmdDoc["sorter_angle"] = sorterAngleForPosition(coinSorterPosition);
  sendDocument(cmdDoc);
}

void handleSecurityLock(JsonDocument &doc) {
  securityArmed = true; // Armed/listening
  lockDoor(true);
  doc.clear();
  doc["status"] = "OK";
  doc["locked"] = true;
  sendDocument(doc);
}

void handleSecurityUnlock(JsonDocument &doc) {
  securityArmed = false; // Disarmed/not listening
  unlockDoor(true);
  doc.clear();
  doc["status"] = "OK";
  doc["locked"] = false;
  sendDocument(doc);
}

void handleSecurityStatus(JsonDocument &doc) {
  doc.clear();
  doc["status"] = "OK";
  doc["locked"] = doorLocked;
  doc["tamper_a"] = tamperLatched;
  sendDocument(doc);
}

void dispatchCommand(char *line) {
  // Parsing from a mutable buffer lets ArduinoJson keep string values in the
  // input buffer instead of duplicating them in the document's memory pool.
  // Capacity is derived from the six-field maximum instead of reserving an
  // arbitrary buffer. String values remain linked to the mutable input buffer.
  StaticJsonDocument<COMMAND_JSON_CAPACITY> cmdDoc;
  DeserializationError err = deserializeJson(cmdDoc, line);
  if (err) {
    currentCommandId = -1;
    sendCommandParseError(cmdDoc, err.c_str(), strlen(line));
    return;
  }

  currentCommandId = cmdDoc["id"] | -1;

  const char *cmd = cmdDoc["cmd"] | "";
  if (strcmp_P(cmd, PSTR("COIN_SESSION_ACK")) == 0) {
    if (cmdDoc["sid"].as<uint32_t>() != currentSessionId || coinAcceptorEnabled) {
      sendCommandError(cmdDoc, "INVALID_PARAM");
      return;
    }
    coinSessionState = COIN_SESSION_CLOSED;
    clearCoinPulseTrain();
    cmdDoc.clear();
    cmdDoc["status"] = "OK";
    sendDocument(cmdDoc);
  } else if (strcmp_P(cmd, PSTR("CAPABILITIES")) == 0) {
    cmdDoc.clear();
    cmdDoc["status"] = "OK";
    cmdDoc["converter_protocol"] = 2;
    sendDocument(cmdDoc);
  } else if (strcmp_P(cmd, PSTR("EMERGENCY_CLEAR")) == 0) {
    tamperLatched = false;
    cmdDoc.clear();
    cmdDoc["status"] = "OK";
    sendDocument(cmdDoc);
  } else if (strcmp_P(cmd, PSTR("PING")) == 0) {
    handlePing(cmdDoc);
  } else if (strcmp_P(cmd, PSTR("VERSION")) == 0) {
    handleVersion(cmdDoc);
  } else if (strcmp_P(cmd, PSTR("RESET")) == 0) {
    handleReset(cmdDoc);
  } else if (strcmp_P(cmd, PSTR("COIN_DISPENSE")) == 0) {
    handleCoinDispense(cmdDoc);
  } else if (strcmp_P(cmd, PSTR("DISPENSE_OPERATION_STATUS")) == 0) {
    handleOperationStatus(cmdDoc);
  } else if (strcmp_P(cmd, PSTR("DISPENSE_OPERATION_ACK")) == 0) {
    handleOperationAck(cmdDoc);
  } else if (strcmp_P(cmd, PSTR("COIN_CHANGE")) == 0) {
    handleCoinChange(cmdDoc);
  } else if (strcmp_P(cmd, PSTR("EMERGENCY_STOP")) == 0) {
    handleEmergencyStop(cmdDoc);
  } else if (strcmp_P(cmd, PSTR("COIN_RESET")) == 0) {
    handleCoinReset(cmdDoc);
  } else if (strcmp_P(cmd, PSTR("COIN_ACCEPTOR_ENABLE")) == 0) {
    handleCoinAcceptorEnable(cmdDoc);
  } else if (strcmp_P(cmd, PSTR("COIN_STATUS")) == 0) {
    handleCoinStatus(cmdDoc);
  } else if (strcmp_P(cmd, PSTR("COIN_SORTER_POSITION")) == 0) {
    handleCoinSorterPosition(cmdDoc);
  } else if (strcmp_P(cmd, PSTR("SECURITY_LOCK")) == 0) {
    handleSecurityLock(cmdDoc);
  } else if (strcmp_P(cmd, PSTR("SECURITY_UNLOCK")) == 0) {
    handleSecurityUnlock(cmdDoc);
  } else if (strcmp_P(cmd, PSTR("SECURITY_STATUS")) == 0) {
    handleSecurityStatus(cmdDoc);
  } else if (strcmp_P(cmd, PSTR("COIN_SESSION_START")) == 0) {
    handleCoinSessionStart(cmdDoc);
  } else if (strcmp_P(cmd, PSTR("COIN_SESSION_STOP")) == 0) {
    handleCoinSessionStop(cmdDoc);
  } else if (strcmp_P(cmd, PSTR("COIN_SESSION_STATUS")) == 0) {
    handleCoinSessionStatus(cmdDoc);
  } else {
    sendCommandError(cmdDoc, "UNKNOWN_CMD");
  }

  currentCommandId = -1;
}

void handleSerialInput() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    lastSerialActivityMs = millis();
    if (c == '\n') {
      if (inputOverflow) {
        currentCommandId = -1;
        sendParseError("INPUT_OVERFLOW", inputLength);
      } else if (inputLength > 0) {
        inputLine[inputLength] = '\0';
        dispatchCommand(inputLine);
      }
      inputLength = 0;
      inputOverflow = false;
    } else if (c != '\r' && !inputOverflow) {
      if (inputLength < SERIAL_INPUT_CAPACITY - 1) {
        inputLine[inputLength++] = c;
      } else {
        inputOverflow = true;
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
  coinSorterServo.detach();
  for (uint8_t i = 0; i < COIN_DISPENSER_COUNT; i++) {
    coinDispensers[i].servo->detach();
  }
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

  pinMode(COIN_PULSE_PIN, INPUT_PULLUP);
  pinMode(COIN_ACCEPTOR_ENABLE_PIN, OUTPUT);
  setCoinAcceptorEnabled(false);
  setupCoinServos();
  setupSecurityPins();
  loadOperationJournal();

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

  static const char HEX_DIGITS[] = "0123456789ABCDEF";
  char uidStr[21] = "";
  size_t offset = 0;
  for (byte i = 0; i < mfrc522.uid.size; i++) {
    if (offset + 2 >= sizeof(uidStr)) break;
    const byte value = mfrc522.uid.uidByte[i];
    uidStr[offset++] = HEX_DIGITS[value >> 4];
    uidStr[offset++] = HEX_DIGITS[value & 0x0F];
  }
  uidStr[offset] = '\0';

  StaticJsonDocument<128> doc;
  doc["event"] = "RFID";
  doc["uid"] = uidStr;
  sendDocument(doc);

  mfrc522.PICC_HaltA();
  mfrc522.PCD_StopCrypto1();
}

void serviceRFIDWhenSerialIdle() {
  const unsigned long now = millis();
  if (Serial.available() > 0 ||
      now - lastSerialActivityMs < SERIAL_ACTIVITY_GUARD_MS ||
      now - lastRfidPollMs < RFID_POLL_INTERVAL_MS) {
    return;
  }
  lastRfidPollMs = now;
  serviceRFID();
}

void loop() {
  // Drain serial before any SPI operation. MFRC522 polling can block long
  // enough to overflow the Uno's 64-byte hardware UART receive ring.
  handleSerialInput();
  serviceTamperEvents();
  serviceTamperBlink();
  serviceSorter();
  serviceCoinHold();
  serviceCoinPulseTrain();
  serviceCoinSessionDrain();
  serviceDispense();
  handleSerialInput();
  serviceRFIDWhenSerialIdle();
  handleSerialInput();
}
