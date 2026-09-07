#pragma once
#include <stdint.h>

// Call from an ISR, or with interrupts disabled. No allocation or I/O.
class TamperFilter {
 public:
  uint32_t sustainMs = 3000;
  uint32_t maxGapMs = 750;
  bool pending = false;
  uint8_t confirmed = 0;  // 1 = A, 2 = B; retained until explicitly cleared.
  uint32_t started = 0;
  uint32_t last = 0;

  void clear() volatile {
    pending = false;
    confirmed = 0;
    seen = 0;
  }

  void expire(uint32_t now) volatile {
    if (pending && !confirmed && uint32_t(now - last) > maxGapMs)
      pending = false;
  }

  void pulse(uint8_t sensor, uint32_t now) volatile {
    if (confirmed) return;
    const uint8_t mask = uint8_t(1U << sensor);
    if ((seen & mask) && uint32_t(now - previous[sensor]) < 250) return;
    seen |= mask;
    previous[sensor] = now;
    expire(now);
    if (!pending) {
      pending = true;
      started = now;
    }
    last = now;
    if (uint32_t(now - started) >= sustainMs) confirmed = sensor + 1;
  }

 private:
  uint8_t seen = 0;
  uint32_t previous[2] = {0, 0};
};
