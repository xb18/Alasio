/**
 * Split a text stream into complete lines.
 *
 * Feed arbitrary chunks to push(); every complete "\n"-terminated line is
 * passed to the onLine callback. A trailing partial line is buffered until
 * the rest of the line arrives, so one push() may invoke onLine zero, one
 * or multiple times.
 *
 * Lines are delivered without the trailing newline. A "\r\n" line keeps
 * the "\r" as part of the line content (matching the raw stream).
 */
export class LineSplitter {
  private buffer = "";
  private readonly onLine: (line: string) => void;

  /**
   * Create a line splitter.
   *
   * Args:
   *     onLine (function): Called once per complete line, without the
   *         trailing newline
   */
  constructor(onLine: (line: string) => void) {
    this.onLine = onLine;
  }

  /**
   * Feed one chunk of the stream.
   *
   * Args:
   *     text (string): Arbitrary chunk, may contain zero, one or multiple
   *         newlines
   */
  push(text: string): void {
    // Fast path: a single complete "\n"-terminated line with nothing
    // pending in the buffer (mprint output, supervisor logs), so hand it
    // off directly without concatenation/slicing.
    const firstNewline = text.indexOf("\n");
    if (!this.buffer && firstNewline >= 0 && firstNewline === text.length - 1) {
      this.onLine(text.slice(0, -1));
      return;
    }
    this.buffer += text;
    let newlineIndex: number;
    while ((newlineIndex = this.buffer.indexOf("\n")) >= 0) {
      this.onLine(this.buffer.slice(0, newlineIndex));
      this.buffer = this.buffer.slice(newlineIndex + 1);
    }
  }
}
