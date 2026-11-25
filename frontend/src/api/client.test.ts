import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "./client";

type FetchArgs = [string, RequestInit];

function mockFetch(body: unknown, init: { status?: number } = {}) {
  const fn = vi.fn(async (..._args: FetchArgs) =>
    new Response(typeof body === "string" ? body : JSON.stringify(body), {
      status: init.status ?? 200,
      headers: { "Content-Type": "application/json" },
    })
  );
  vi.stubGlobal("fetch", fn);
  return fn;
}

afterEach(() => vi.unstubAllGlobals());

describe("api client", () => {
  it("does not send a JSON content-type on bodiless GETs", async () => {
    const fetchFn = mockFetch({ documents: {}, changes: {}, alerts: {}, impact_items: {} });
    await api.stats();
    const [url, init] = fetchFn.mock.calls[0];
    expect(url).toBe("/api/v1/dashboard/stats");
    expect(new Headers(init.headers).has("Content-Type")).toBe(false);
  });

  it("sends JSON bodies with a content-type for POSTs", async () => {
    const fetchFn = mockFetch({ detail: "ok", status: "approved" });
    await api.alerts.review("a1", "i1", "approved", "fine");
    const [url, init] = fetchFn.mock.calls[0];
    expect(url).toBe("/api/v1/alerts/a1/items/i1/review");
    expect(init.method).toBe("POST");
    expect(new Headers(init.headers).get("Content-Type")).toBe("application/json");
    expect(JSON.parse(init.body as string)).toEqual({ status: "approved", reviewer_notes: "fine" });
  });

  it("unwraps paginated list responses", async () => {
    mockFetch({ items: [{ id: "x" }], total: 1, page: 1, page_size: 20, pages: 1 });
    await expect(api.alerts.list()).resolves.toEqual([{ id: "x" }]);
  });

  it("throws with status and body on HTTP errors", async () => {
    mockFetch('{"detail":"Role required"}', { status: 403 });
    await expect(api.stats()).rejects.toThrow(/^403 .*Role required/);
  });

  it("encodes query parameters", async () => {
    const fetchFn = mockFetch({ items: [], total: 0, page: 1, page_size: 20, pages: 1 });
    await api.documents.list("SEC & CNBV");
    expect(fetchFn.mock.calls[0][0]).toBe("/api/v1/documents/?source=SEC%20%26%20CNBV");
  });
});
