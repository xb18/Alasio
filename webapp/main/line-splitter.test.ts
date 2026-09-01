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
  assert.deepEqual(collect(["\r\n"]), [""]);
});

test("LineSplitter: CRLF line ending is stripped", () => {
  // Windows pipes deliver CRLF; the trailing "\r" is part of the line
  // ending, not the line content.
  assert.deepEqual(collect(["a\r\n"]), ["a"]);
  assert.deepEqual(collect(["a\r\n", "b\n"]), ["a", "b"]);
});

test("LineSplitter: CRLF split across pushes", () => {
  assert.deepEqual(collect(["hel", "lo\r\n"]), ["hello"]);
  assert.deepEqual(collect(["a\r", "b\n"]), ["a\rb"]);
});

test("LineSplitter: carriage return inside the line is kept", () => {
  // Only the line-ending "\r" of a CRLF line is stripped; a "\r"
  // anywhere else in the line is raw content.
  assert.deepEqual(collect(["a\rb\n"]), ["a\rb"]);
});
