import { describe, expect, it } from "vitest";
import { readSSE, type SSEEvent } from "./sse";

function streamOf(chunks: string[], status = 200): Response {
  const enc = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      chunks.forEach((c) => controller.enqueue(enc.encode(c)));
      controller.close();
    },
  });
  return new Response(body, { status });
}

describe("readSSE", () => {
  it("parses events split across chunks and skips malformed lines", async () => {
    const events: SSEEvent[] = [];
    await readSSE(
      streamOf(['data: {"type":"tok', 'en","text":"a"}\n\n', "data: {oops}\n\n", 'data: {"type":"done"}']),
      (e) => events.push(e),
    );
    expect(events).toEqual([{ type: "token", text: "a" }, { type: "done" }]);
  });

  it("throws on an error status", async () => {
    await expect(readSSE(streamOf(["forbidden"], 403), () => {})).rejects.toThrow("403");
  });
});
