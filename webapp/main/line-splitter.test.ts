/**
 * Unit tests for LineSplitter.
 *
 * Run with: npx tsx --test webapp/main/line-splitter.test.ts
 */
import assert from "node:assert/strict";
import { test } from "node:test";
import { LineSplitter } from "./line-splitter";

const collect = (chunks: string[]): string[] => {
  const lines: string[] = [];
  const splitter = new LineSplitter((line) => lines.push(line));
  for (const chunk of chunks) {
    splitter.push(chunk);
  }
  return lines;
};

test("LineSplitter: single complete line in one push (fast path)", () => {
  assert.deepEqual(collect(["hello\n"]), ["hello"]);
});

test("LineSplitter: consecutive complete lines (fast path per push)", () => {
  assert.deepEqual(collect(["a\n", "b\n", "c\n"]), ["a", "b", "c"]);
});

test("LineSplitter: line split across pushes", () => {
  assert.deepEqual(collect(["hel", "lo\n"]), ["hello"]);
});

test("LineSplitter: multiple lines in one push", () => {
  assert.deepEqual(collect(["a\nb\nc\n"]), ["a", "b", "c"]);
});

test("LineSplitter: multiple lines without trailing newline", () => {
  assert.deepEqual(collect(["a\nb"]), ["a"]);
  assert.deepEqual(collect(["a\nb", "\n"]), ["a", "b"]);
});

test("LineSplitter: partial line without newline stays buffered", () => {
  assert.deepEqual(collect(["hello"]), []);
});

test("LineSplitter: partial line completes on a later push", () => {
  assert.deepEqual(collect(["hello", " world\n"]), ["hello world"]);
});

test("LineSplitter: complete line then partial buffer", () => {
  assert.deepEqual(collect(["a\nbc"]), ["a"]);
  assert.deepEqual(collect(["a\nbc", "d\n"]), ["a", "bcd"]);
});

test("LineSplitter: empty push", () => {
  assert.deepEqual(collect([""]), []);
});

test("LineSplitter: empty line", () => {
  assert.deepEqual(collect(["\n"]), [""]);
});

test("LineSplitter: CRLF keeps \\r as part of the line content", () => {
  assert.deepEqual(collect(["a\r\n"]), ["a\r"]);
});
