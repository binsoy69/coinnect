#!/usr/bin/env node
// Run the compiled Uno HEX in avr8js 0.21.1; no physical hardware is accessed.
// See firmware/README.md for dependency setup and invocation.
const fs = require('node:fs');
const assert = require('node:assert/strict');
const avr = require('avr8js');

assert(process.argv[2], 'Usage: node scripts/test_uno_serial.cjs <firmware.hex>');
const flash = new Uint8Array(32768);
for (const line of fs.readFileSync(process.argv[2], 'utf8').trim().split(/\r?\n/)) {
  assert.match(line, /^:[0-9a-f]+$/i);
  const bytes = Buffer.from(line.slice(1), 'hex');
  assert.equal(bytes.length, bytes[0] + 5, 'Invalid HEX record length');
  assert.equal(bytes.reduce((sum, byte) => sum + byte, 0) & 255, 0, 'HEX checksum');
  if (bytes[3] === 0) {
    flash.set(bytes.subarray(4, 4 + bytes[0]), bytes.readUInt16BE(1));
  } else {
    // Uno images use 16-bit addresses. Ignore EOF/start-address records only.
    assert([1, 3, 5].includes(bytes[3]), 'Unsupported HEX address extension');
  }
}

const cpu = new avr.CPU(new Uint16Array(flash.buffer), 2048);
for (const config of [avr.timer0Config, avr.timer1Config, avr.timer2Config]) {
  new avr.AVRTimer(cpu, config);
}
const ports = [avr.portBConfig, avr.portCConfig, avr.portDConfig].map(config => new avr.AVRIOPort(cpu, config));
const eeprom = new avr.EEPROMMemoryBackend(1024);
eeprom.memory.fill(255);
new avr.AVREEPROM(cpu, eeprom);
const spi = new avr.AVRSPI(cpu, avr.spiConfig, 16000000);
spi.onTransfer = () => 0; // Stub RFID register reads; no card is present.
const uart = new avr.AVRUSART(cpu, avr.usart0Config, 16000000);
const lines = [];
const tamperEvents = [];
uart.onLineTransmit = line => {
  const data = JSON.parse(line);
  lines.push(data);
  if (data.event === "TAMPER") tamperEvents.push(data);
};
let minSP = 2303;

function run(cycles) {
  const end = cpu.cycles + cycles;
  while (cpu.cycles < end) {
    assert(cpu.pc !== 0 || cpu.cycles < 10000, 'Unexpected firmware restart');
    const wasEnabled = cpu.interruptsEnabled;
    avr.avrInstruction(cpu);
    // AVR8js services interrupts immediately in tick(). Defer delivery for
    // one instruction when restoring I, so avr-gcc's SPH/SREG/SPL stack
    // update sequence completes before an ISR uses the new stack pointer.
    // Keep clock events running during that instruction.
    const justEnabled = !wasEnabled && cpu.interruptsEnabled;
    if (justEnabled) cpu.data[95] &= 127;
    cpu.tick();
    if (justEnabled) cpu.data[95] |= 128;
    if (cpu.cycles > 10000) minSP = Math.min(minSP, cpu.SP);
  }
}

run(16000000);
assert(lines.some(line => line.event === 'READY'), 'Firmware must boot');
lines.length = 0;
let id = 0;
let paceSerial = false;
function command(payload) {
  const request = {...payload, id: ++id};
  // Match the backend's resync/chunk pacing after long idle sensor tests.
  if (paceSerial) { assert(uart.writeByte(10)); run(800000); }
  let sent = 0;
  for (const byte of Buffer.from(JSON.stringify(request) + '\n')) {
    assert(uart.writeByte(byte), 'UART must accept each byte');
    run(1800); // Slightly slower than 115200 baud, with timer interrupts live.
    if (++sent % 16 === 0 && paceSerial) run(320000);
  }
  for (let i = 0; i < 2000 && !lines.some(line => line.id === id); i++) run(16000);
  const response = lines.find(line => line.id === id);
  assert(response, `No response for ${JSON.stringify(request)}`);
  if (request.operation_id) assert.equal(response.operation_id, request.operation_id);
  lines.length = 0;
  return response;
}

for (let i = 0; i < 25; i++) {
  const operation_id = `82c0867c-3f76-46ac-8040-${String(i).padStart(12, '0')}`;
  assert.equal(command({cmd: 'CAPABILITIES'}).converter_protocol, 2);
  assert.equal(command({cmd: 'DISPENSE_OPERATION_STATUS', operation_id}).operation_status, 'NOT_FOUND');
  const ack = command({cmd: 'DISPENSE_OPERATION_ACK', operation_id});
  assert.equal(ack.status, 'ERROR');
  assert.equal(ack.code, 'NOT_FOUND');
  assert.equal(command({cmd: 'PING'}).message, 'PONG');
  // Exercise the largest command response after UUID-bearing responses.
  const status = command({cmd: 'COIN_STATUS'});
  assert.deepEqual(status, {
    status: 'OK', acceptor_enabled: false, sorter_position: 'CENTER',
    sorter_angle: 81, session_total: 0, id,
  });
  assert.equal(command({cmd: 'COIN_SESSION_STATUS', denom: 20}).session_state, 'IDLE');
}
const version = command({cmd: 'VERSION'}).version;
console.log(JSON.stringify({passed: true, commands: id, minSP, version}));


paceSerial = true;

// Exercise real external interrupt D3 and pin-change interrupt A0 wiring.
function pulse(sensor, durationMs = 310) {
  const port = sensor === 0 ? ports[2] : ports[1];
  const pin = sensor === 0 ? 3 : 0;
  port.setPin(pin, true);
  run(16000);
  port.setPin(pin, false);
  run((durationMs - 1) * 16000);
}
function configure(sustain_ms = 3000, max_gap_ms = 750) {
  const result = command({cmd: 'SECURITY_CONFIG', sustain_ms, max_gap_ms});
  assert.equal(result.status, 'OK');
  assert.equal(result.sustain_ms, sustain_ms);
  assert.equal(result.max_gap_ms, max_gap_ms);
}
configure();
for (const values of [[250, 250], [3000, 249], [3000, 3000], [60001, 750],
                      [-1, 750], [3000.5, 750], ['3000', 750], [true, 750]]) {
  assert.equal(command({cmd: 'SECURITY_CONFIG', sustain_ms: values[0], max_gap_ms: values[1]}).code, 'INVALID_PARAM');
}
assert.equal(command({cmd: 'SECURITY_CONFIG'}).code, 'INVALID_PARAM');
command({cmd: 'SECURITY_LOCK'});
pulse(0);
run(4 * 16000000);
assert.equal(tamperEvents.length, 0);
// A held HIGH is one edge, not continuous tampering.
ports[2].setPin(3, true);
run(4 * 16000000);
ports[2].setPin(3, false);
assert.equal(tamperEvents.length, 0);
for (let mode = 0; mode < 3; mode++) {
  command({cmd: 'EMERGENCY_CLEAR'});
  const before = tamperEvents.length;
  for (let i = 0; i < 10; i++) pulse(mode === 2 ? i % 2 : mode);
  assert.equal(tamperEvents.length, before);
  pulse(mode === 1 ? 1 : 0);
  assert.equal(tamperEvents.length, before + 1);
  for (let i = 0; i < 4; i++) pulse(0);
  assert.equal(tamperEvents.length, before + 1);
  configure();
  assert.equal(command({cmd: 'SECURITY_STATUS'}).tamper_a, true);
}
command({cmd: 'EMERGENCY_CLEAR'});
const before = tamperEvents.length;
for (let i = 0; i < 8; i++) pulse(0);
run(751 * 16000);
for (let i = 0; i < 8; i++) pulse(1);
assert.equal(tamperEvents.length, before);
command({cmd: 'SECURITY_UNLOCK'});
for (let i = 0; i < 16; i++) pulse(0);
assert.equal(tamperEvents.length, before);
command({cmd: 'SECURITY_LOCK'});
pulse(0);
assert.equal(tamperEvents.length, before);
command({cmd: 'EMERGENCY_STOP'});
assert.equal(command({cmd: 'SECURITY_STATUS'}).tamper_a, true);
console.log(JSON.stringify({tamperPassed: true, confirmedEvents: tamperEvents.length}));
