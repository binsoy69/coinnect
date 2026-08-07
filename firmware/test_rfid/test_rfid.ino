#include <Arduino.h>
#include <SPI.h>
#include <MFRC522.h>

// Standalone MFRC522 RFID Reader bench test for Coinnect Uno wiring.
// The MFRC522 RFID module operates strictly at 3.3V VCC.
// Do NOT connect to 5V VCC as it will destroy the RFID chip.

static const uint8_t MFRC522_RST_PIN = A1;  // D15 on Uno
static const uint8_t MFRC522_SS_PIN = 10;   // Hardware SS pin on Uno

MFRC522 mfrc522(MFRC522_SS_PIN, MFRC522_RST_PIN);

void setup() {
  Serial.begin(115200);

  while (!Serial) {
    ; // Wait for serial monitor to open
  }

  Serial.println(F("=================================================="));
  Serial.println(F("Coinnect Uno RFID (MFRC522) Bench Test"));
  Serial.println(F("=================================================="));
  Serial.println(F("Wiring requirements:"));
  Serial.println(F("  RFID VCC  -> Uno 3.3V (CRITICAL: Do NOT use 5V!)"));
  Serial.println(F("  RFID GND  -> Uno GND"));
  Serial.println(F("  RFID RST  -> Uno A1 (D15)"));
  Serial.println(F("  RFID SDA  -> Uno D10 (SS)"));
  Serial.println(F("  RFID MOSI -> Uno D11 (MOSI)"));
  Serial.println(F("  RFID MISO -> Uno D12 (MISO)"));
  Serial.println(F("  RFID SCK  -> Uno D13 (SCK)"));
  Serial.println(F("=================================================="));

  // Initialize SPI bus
  SPI.begin();

  // Initialize MFRC522 card reader
  mfrc522.PCD_Init();
  delay(10);

  // Set antenna gain to maximum
  mfrc522.PCD_SetAntennaGain(MFRC522::RxGain_max);

  // Perform startup diagnostics
  Serial.println(F("Running diagnostics..."));

  byte version = mfrc522.PCD_ReadRegister(MFRC522::VersionReg);

  Serial.print(F("PCD Version Register: 0x"));
  Serial.print(version, HEX);

  if (version == 0x91) {
    Serial.println(F(" (MFRC522 v1.0 detected)"));
  } else if (version == 0x92) {
    Serial.println(F(" (MFRC522 v2.0 detected)"));
  } else if (version == 0x88) {
    Serial.println(F(" (FM17522 clone detected)"));
  } else {
    Serial.println(F(" (Unknown chip)"));
  }

  if (version == 0x00 || version == 0xFF) {
    Serial.println(F("ERROR: Communication with MFRC522 failed!"));
    Serial.println(F("Please verify your SPI wiring and make sure the reader has 3.3V power."));
    Serial.println(F("Testing halted."));

    while (true) {
      ; // Halt execution
    }
  }

  Serial.println(F("SPI Communication: OK"));
  Serial.println(F("=================================================="));
  Serial.println(F("Ready! Place an RFID card/keychain near the reader..."));
  Serial.println(F("=================================================="));
}

void loop() {
  // Look for a new card
  if (!mfrc522.PICC_IsNewCardPresent()) {
    return;
  }

  // Read the card serial
  if (!mfrc522.PICC_ReadCardSerial()) {
    return;
  }

  // Print UID
  Serial.print(F("Card Detected! UID HEX: "));

  for (byte i = 0; i < mfrc522.uid.size; i++) {
    if (mfrc522.uid.uidByte[i] < 0x10) {
      Serial.print(F("0"));
    }

    Serial.print(mfrc522.uid.uidByte[i], HEX);
  }

  Serial.print(F(" | Size: "));
  Serial.print(mfrc522.uid.size);

  Serial.print(F(" bytes | Type: "));

  MFRC522::PICC_Type piccType =
      mfrc522.PICC_GetType(mfrc522.uid.sak);

  Serial.println(mfrc522.PICC_GetTypeName(piccType));

  // Halt PICC
  mfrc522.PICC_HaltA();

  // Stop encryption
  mfrc522.PCD_StopCrypto1();

  delay(1000);
}