// Execute the timing test sketch on an emulated Uno; no hardware is accessed.
const fs = require('node:fs');
const assert = require('node:assert/strict');
const avr = require('avr8js');
assert(process.argv[2], 'Usage: node scripts/test_tamper_filter.cjs <test-sketch.hex>');
const flash = new Uint8Array(32768);
for (const line of fs.readFileSync(process.argv[2], 'utf8').trim().split(/\r?\n/)) {
  const bytes = Buffer.from(line.slice(1), 'hex');
  assert.equal(bytes.reduce((sum, byte) => sum + byte, 0) & 255, 0);
  if (bytes[3] === 0) flash.set(bytes.subarray(4, 4 + bytes[0]), bytes.readUInt16BE(1));
  else assert([1, 3, 5].includes(bytes[3]));
}
const cpu = new avr.CPU(new Uint16Array(flash.buffer), 2048);
new avr.AVRTimer(cpu, avr.timer0Config);
const uart = new avr.AVRUSART(cpu, avr.usart0Config, 16000000);
let passed = false;
uart.onLineTransmit = line => {
  assert(!line.startsWith('FAIL'), line);
  if (line.startsWith('PASS')) { passed = true; console.log(line); }
};
while (cpu.cycles < 16000000 && !passed) {
  avr.avrInstruction(cpu);
  cpu.tick();
}
assert(passed, 'Timing test did not complete');
