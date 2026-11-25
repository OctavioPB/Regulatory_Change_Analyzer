/** Minimal reader for the backend's `data: {json}\n\n` Server-Sent Events. */

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type SSEEvent = { type: string; [key: string]: any };

/**
 * Read an SSE response to the end, calling `onEvent` for every JSON event.
 * Throws on a non-2xx status; malformed lines are skipped.
 */
export async function readSSE(res: Response, onEvent: (evt: SSEEvent) => void): Promise<void> {
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  if (!res.body) throw new Error("No response body");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const handle = (line: string) => {
    if (!line.startsWith("data: ")) return;
    let evt: SSEEvent;
    try {
      evt = JSON.parse(line.slice(6));
    } catch {
      return; // malformed line
    }
    onEvent(evt);
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    lines.forEach(handle);
  }
  buffer += decoder.decode();
  if (buffer) handle(buffer);
}
