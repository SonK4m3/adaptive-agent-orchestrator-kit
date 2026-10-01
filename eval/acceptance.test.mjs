import test from 'node:test';
import assert from 'node:assert/strict';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

if (!process.env.ORCHESTRATOR_FIXTURE) throw new Error('Set ORCHESTRATOR_FIXTURE to an isolated implemented fixture directory');
const base = resolve(process.env.ORCHESTRATOR_FIXTURE);
const { parseDuration } = await import(pathToFileURL(resolve(base, 'duration.mjs')));
const { groupByStatus } = await import(pathToFileURL(resolve(base, 'grouping.mjs')));

test('R1 conversions and zero', () => {
  for (const [input, expected] of [['90s',90],['2m',120],['3h',10800],[' 0s ',0],['01m',60]]) assert.equal(parseDuration(input), expected);
});
test('R2 nonstrings', () => {
  for (const input of [null, undefined, 2, {}, ['1s']]) assert.throws(() => parseDuration(input), TypeError);
});
test('R2 invalid syntax', () => {
  for (const input of ['', '-1s','1.5h','2M','1d','1 s','1e3s','1s\n2s']) assert.throws(() => parseDuration(input), RangeError);
});
test('R2 safe integer boundary', () => {
  assert.equal(parseDuration('9007199254740991s'), Number.MAX_SAFE_INTEGER);
  assert.throws(() => parseDuration('9007199254740992s'), RangeError);
  assert.throws(() => parseDuration('9007199254740991h'), RangeError);
});
test('R3 first appearance and duplicates', () => {
  assert.deepEqual(groupByStatus([{id:'a',status:'open'},{id:'b',status:'done'},{id:'a',status:'open'}]), [{status:'open',ids:['a','a']},{status:'done',ids:['b']}]);
  assert.deepEqual(groupByStatus([{id:'z',status:'done'},{id:'b',status:'open'},{id:'a',status:'done'}]), [{status:'done',ids:['z','a']},{status:'open',ids:['b']}]);
});
test('R3 special and empty values', () => {
  assert.deepEqual(groupByStatus([]), []);
  assert.deepEqual(groupByStatus([{id:'',status:'__proto__'},{id:'z',status:''}]), [{status:'__proto__',ids:['']},{status:'',ids:['z']}]);
});
test('R4 rejects malformed input', () => {
  for (const input of [null, {}, 'records', [null], [{}], [{id:1,status:'a'}], [{id:'a',status:1}]]) assert.throws(() => groupByStatus(input), TypeError);
});
test('R4 frozen input remains unchanged', () => {
  const input = Object.freeze([Object.freeze({id:'a',status:'open'}),Object.freeze({id:'b',status:'open'})]);
  assert.deepEqual(groupByStatus(input), [{status:'open',ids:['a','b']}]);
  assert.deepEqual(input, [{id:'a',status:'open'},{id:'b',status:'open'}]);
});
