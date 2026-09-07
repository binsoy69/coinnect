#include <TamperFilter.h>

uint16_t checks = 0;
void check(bool ok) {
  ++checks;
  if (!ok) {
    Serial.print(F("FAIL "));
    Serial.println(checks);
  }
}

void setup() {
  Serial.begin(115200);
  volatile TamperFilter f;
  // Single edge / held HIGH cannot qualify merely by waiting.
  f.pulse(0, 0);
  f.expire(750);
  check(f.pending && !f.confirmed);
  f.expire(751);
  check(!f.pending && !f.confirmed);
  f.expire(3000);
  check(!f.confirmed);
  // Same rule for A, B and alternating sensors, including simultaneous edges.
  for (uint8_t mode = 0; mode < 3; ++mode) {
    f.clear();
    for (uint32_t t = 0; t < 3000; t += 250) {
      f.pulse(mode == 2 ? (t / 250) % 2 : mode, t);
      check(!f.confirmed);
    }
    f.pulse(mode == 1 ? 1 : 0, 3000);
    check(f.confirmed != 0);
    const uint8_t source = f.confirmed;
    f.pulse(1, 4000);
    f.expire(8000);
    check(f.confirmed == source); // Delayed service preserves confirmation.
  }
  f.clear();
  f.pulse(0, 100);
  f.pulse(1, 100);
  check(!f.confirmed && f.started == 100);
  f.pulse(0, 349);
  check(f.last == 100); // Per-sensor debounce.
  f.pulse(0, 350);
  check(f.last == 350);
  // Gap exactly 750 remains continuous; 751 resets, without main-loop service.
  f.clear();
  for (uint32_t t = 0; t <= 2250; t += 750) f.pulse(0, t);
  f.pulse(0, 3001);
  check(!f.confirmed && f.started == 3001);
  for (uint32_t t = 3751; t <= 6001; t += 750) f.pulse(0, t);
  check(f.confirmed == 1);
  // Unsigned arithmetic across millis rollover.
  f.clear();
  const uint32_t start = UINT32_MAX - 1000;
  for (uint32_t t = 0; t <= 3000; t += 250) f.pulse(0, start + t);
  check(f.confirmed == 1);
  f.clear();
  check(!f.pending && !f.confirmed);
  f.pulse(0, 10);
  check(f.pending && f.started == 10); // Old debounce timestamps cleared too.
  f.clear();
  f.sustainMs = 1000;
  f.maxGapMs = 250;
  for (uint32_t t = 0; t <= 1000; t += 250) f.pulse(1, t);
  check(f.confirmed == 2);
  Serial.print(F("PASS "));
  Serial.println(checks);
}

void loop() {}
