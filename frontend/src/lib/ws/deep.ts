type Key = string | number;

/**
 * Performs an in-place deep set on an object or array.
 * Creates path segments if they don't exist. This function mutates the object directly.
 * @param obj The target object or array to modify.
 * @param path An array of keys representing the path.
 * @param value The value to set at the path.
 */
export function deepSet(obj: any, path: Key[], value: any): void {
  if (path.length === 0) {
    // This case implies replacing the object and should be handled by the caller.
    return;
  }

  let current = obj;
  const lastIndex = path.length - 1;
  const lastKey = path[lastIndex];
  for (let i = 0; i < lastIndex; i++) {
    const key = path[i];
    const next = current[key];
    if (next === undefined || next === null || typeof next !== "object") {
      // Create an array if the next key is a number, otherwise create an object.
      // The container is written through the proxy (making it reactive) and
      // then re-read: the proxy stores a proxied copy, so mutating `next`
      // directly would bypass reactivity.
      current[key] = typeof path[i + 1] === "number" ? [] : {};
      current = current[key];
    } else {
      // `next` was read through the proxy, so it can be reused directly.
      current = next;
    }
  }

  current[lastKey] = value;
}

/**
 * Performs an in-place deep delete on an object or array.
 * This function mutates the object directly.
 * @param obj The target object or array to modify.
 * @param path An array of keys representing the path to the property to delete.
 */
export function deepDel(obj: any, path: Key[]): void {
  if (path.length === 0) {
    return; // Deleting with an empty path is a no-op.
  }

  let current = obj;
  const lastIndex = path.length - 1;
  const lastKey = path[lastIndex];
  // Traverse to the parent of the target property.
  for (let i = 0; i < lastIndex; i++) {
    const key = path[i];
    const next = current[key];
    // If the path doesn't exist, there's nothing to delete.
    if (next === undefined || next === null || typeof next !== "object") {
      return;
    }
    current = next;
  }

  // Delete the target property from its parent.
  delete current[lastKey];
}
