import { describe, expect, it } from "vitest";
import { deepDel, deepSet } from "./deep";

describe("TestDeepSet", () => {
  it("creates missing intermediate object paths", () => {
    const obj: Record<string, any> = {};
    deepSet(obj, ["a", "b"], 1);
    expect(obj).toEqual({ a: { b: 1 } });
  });

  it("creates an array when the next path key is a number", () => {
    const obj: Record<string, any> = {};
    deepSet(obj, ["list", 0], "first");
    expect(obj).toEqual({ list: ["first"] });
  });

  it("creates nested arrays for numeric keys at any depth", () => {
    const obj: Record<string, any> = {};
    deepSet(obj, ["a", 1, "b"], 2);
    expect(obj).toEqual({ a: [undefined, { b: 2 }] });
  });

  it("sets the leaf value in place on an existing path", () => {
    const obj = { a: { b: { c: 1 } } };
    deepSet(obj, ["a", "b", "c"], 2);
    expect(obj).toEqual({ a: { b: { c: 2 } } });
  });

  it("keeps sibling fields when traversing an existing path", () => {
    const obj = { a: { keep: true, b: 1 } };
    deepSet(obj, ["a", "b"], 2);
    expect(obj).toEqual({ a: { keep: true, b: 2 } });
  });

  it("replaces a non-object intermediate value", () => {
    const obj: Record<string, any> = { a: "scalar" };
    deepSet(obj, ["a", "b"], 1);
    expect(obj).toEqual({ a: { b: 1 } });
  });

  it("replaces a null intermediate value", () => {
    const obj: Record<string, any> = { a: null };
    deepSet(obj, ["a", "b"], 1);
    expect(obj).toEqual({ a: { b: 1 } });
  });

  it("is a no-op for an empty path (caller replaces the root)", () => {
    const obj = { a: 1 };
    deepSet(obj, [], 2);
    expect(obj).toEqual({ a: 1 });
  });

  it("mutates the passed object, not a copy", () => {
    const obj = {};
    deepSet(obj, ["a"], 1);
    expect(obj).toHaveProperty("a", 1);
  });
});

describe("TestDeepDel", () => {
  it("deletes a leaf value", () => {
    const obj = { a: { b: 1, c: 2 } };
    deepDel(obj, ["a", "b"]);
    expect(obj).toEqual({ a: { c: 2 } });
  });

  it("deletes an array element by index (delete semantics, leaving a hole)", () => {
    const obj = { list: ["x", "y", "z"] };
    deepDel(obj, ["list", 1]);
    // deepDel uses the `delete` operator: the element is removed, the
    // array keeps its length with a hole at the deleted index.
    expect(obj.list).toHaveLength(3);
    expect(obj.list[1]).toBeUndefined();
    expect(obj.list[0]).toBe("x");
    expect(obj.list[2]).toBe("z");
  });

  it("is a no-op when the leaf path does not exist", () => {
    const obj = { a: { b: 1 } };
    deepDel(obj, ["a", "missing"]);
    expect(obj).toEqual({ a: { b: 1 } });
  });

  it("is a no-op when an intermediate path does not exist", () => {
    const obj = { a: {} };
    deepDel(obj, ["a", "b", "c"]);
    expect(obj).toEqual({ a: {} });
  });

  it("is a no-op when an intermediate value is a scalar", () => {
    const obj = { a: 1 };
    deepDel(obj, ["a", "b"]);
    expect(obj).toEqual({ a: 1 });
  });

  it("is a no-op for an empty path (caller replaces the root)", () => {
    const obj = { a: 1 };
    deepDel(obj, []);
    expect(obj).toEqual({ a: 1 });
  });
});
