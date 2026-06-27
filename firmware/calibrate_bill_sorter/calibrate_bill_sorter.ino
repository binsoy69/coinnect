#include <Arduino.h>
#include <AccelStepper.h>

static const uint8_t STEP_PIN = 6;
static const uint8_t DIR_PIN = 7;
static const uint8_t ENABLE_PIN = 4;
static const uint8_t LIMIT_PIN = 5;

static const long HOME_SPEED_STEPS_PER_SEC = -7500;
static const long HOME_BACKOFF_STEPS = 800;
static const unsigned long HOME_TIMEOUT_MS = 60000;

static const float SORT_MAX_SPEED = 12000.0;
static const float SORT_ACCELERATION = 30000.0;

static const long DEFAULT_SLOT_POSITIONS[8] = {
    2920, 8760, 14600, 20440, 26280, 32120, 37960, 43800
};

AccelStepper sorter(AccelStepper::DRIVER, STEP_PIN, DIR_PIN);
bool sorterHomed = false;

void enableStepper() {
    digitalWrite(ENABLE_PIN, LOW);
}

void disableStepper() {
    digitalWrite(ENABLE_PIN, HIGH);
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

bool homeSorter() {
    Serial.println("Homing sorter...");
    enableStepper();
    sorter.setMaxSpeed(abs(HOME_SPEED_STEPS_PER_SEC));
    sorter.setAcceleration(SORT_ACCELERATION);
    sorter.setSpeed(HOME_SPEED_STEPS_PER_SEC);

    const unsigned long startedAt = millis();
    while (!limitTriggered()) {
        sorter.runSpeed();
        if (millis() - startedAt > HOME_TIMEOUT_MS) {
            sorter.stop();
            disableStepper();
            sorterHomed = false;
            Serial.println("ERROR: Homing timed out.");
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
    Serial.println("Homing completed. Position set to 0.");
    return true;
}

void moveRelative(long steps) {
    if (!sorterHomed) {
        Serial.println("ERROR: Sorter not homed. Send 'H' first.");
        return;
    }
    enableStepper();

    long target = sorter.currentPosition() + steps;
    float speed = (steps > 0) ? SORT_MAX_SPEED : -SORT_MAX_SPEED;

    Serial.print("Moving to target position: ");
    Serial.println(target);

    sorter.setMaxSpeed(SORT_MAX_SPEED);
    sorter.setSpeed(speed);

    while ((steps > 0 && sorter.currentPosition() < target) ||
           (steps < 0 && sorter.currentPosition() > target)) {
        sorter.runSpeed();
    }

    Serial.print("Current position: ");
    Serial.println(sorter.currentPosition());
}

void moveToSlot(int slot) {
    if (slot < 1 || slot > 8) {
        Serial.println("ERROR: Invalid slot number. Choose 1-8.");
        return;
    }
    long target = DEFAULT_SLOT_POSITIONS[slot - 1];
    long relativeSteps = target - sorter.currentPosition();
    moveRelative(relativeSteps);
}

void setup() {
    Serial.begin(115200);
    pinMode(STEP_PIN, OUTPUT);
    pinMode(DIR_PIN, OUTPUT);
    pinMode(ENABLE_PIN, OUTPUT);
    pinMode(LIMIT_PIN, INPUT_PULLUP);
    
    disableStepper();
    Serial.println("=== Bill Sorter Calibration Utility ===");
    Serial.println("Commands:");
    Serial.println("  H         - Perform homing sequence");
    Serial.println("  +<steps>  - Jog positive (e.g. +100)");
    Serial.println("  -<steps>  - Jog negative (e.g. -100)");
    Serial.println("  S<slot>   - Move to default slot (1-8, e.g. S3)");
    Serial.println("  P         - Print current position");
    Serial.println("  E0        - Disable motor holding torque");
    Serial.println("  E1        - Enable motor holding torque");
}

void loop() {
    if (Serial.available() > 0) {
        String input = Serial.readStringUntil('\n');
        input.trim();
        if (input.length() == 0) return;
        
        char cmd = input.charAt(0);
        
        if (cmd == 'H' || cmd == 'h') {
            homeSorter();
        } else if (cmd == 'P' || cmd == 'p') {
            Serial.print("Current Position: ");
            Serial.println(sorter.currentPosition());
        } else if (cmd == 'E' || cmd == 'e') {
            if (input.length() > 1 && input.charAt(1) == '0') {
                disableStepper();
                Serial.println("Stepper disabled.");
            } else {
                enableStepper();
                Serial.println("Stepper enabled.");
            }
        } else if (cmd == '+' || cmd == '-') {
            long steps = input.toInt();
            if (steps != 0) {
                moveRelative(steps);
            } else {
                Serial.println("ERROR: Invalid step format.");
            }
        } else if (cmd == 'S' || cmd == 's') {
            int slot = input.substring(1).toInt();
            moveToSlot(slot);
        } else {
            Serial.println("ERROR: Unknown command.");
        }
    }
}
