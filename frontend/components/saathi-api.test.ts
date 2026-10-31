import { afterEach, describe, expect, it, vi } from "vitest";
import { saathiApi, SaathiApiError } from "./saathi-api";

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

describe("Saathi API client", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("loads backend health through the same-origin API proxy", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ status: "ok", database: "connected", llm_configured: false, whatsapp_configured: false }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(saathiApi.health()).resolves.toMatchObject({ database: "connected" });
    expect(fetchMock).toHaveBeenCalledWith("/api/health", expect.objectContaining({ headers: expect.any(Headers) }));
  });

  it("loads every merchant page when the backend has more than 300 records", async () => {
    const first = { items: [{ id: "m_first" }], total: 2, page: 1, limit: 1 };
    const second = { items: [{ id: "m_second" }], total: 2, page: 2, limit: 1 };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse(first))
      .mockResolvedValueOnce(jsonResponse(second));
    vi.stubGlobal("fetch", fetchMock);

    await expect(saathiApi.merchants()).resolves.toMatchObject({
      total: 2,
      items: [{ id: "m_first" }, { id: "m_second" }],
    });
    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/merchants?page=1&limit=300&sort=score", expect.any(Object));
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/merchants?page=2&limit=300&sort=score", expect.any(Object));
  });

  it("sends merchant chat text as JSON and returns the persisted agent response", async () => {
    const result = { reply: "We can help with that.", action: null, merchant_state: "ENGAGED" };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(result));
    vi.stubGlobal("fetch", fetchMock);

    await expect(saathiApi.sendMessage("m_example", "Can you explain the fees?")).resolves.toEqual(result);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/chat/m_example/message",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ text: "Can you explain the fees?" }),
      }),
    );
    expect(fetchMock.mock.calls[0][1]?.headers).toHaveProperty("get");
    expect((fetchMock.mock.calls[0][1]?.headers as Headers).get("Content-Type")).toBe("application/json");
  });

  it("surfaces API errors instead of returning demo-shaped data", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      jsonResponse({ error: { code: "UNAUTHORIZED", message: "Valid staff API credentials are required." } }, 401),
    ));

    await expect(saathiApi.actions()).rejects.toMatchObject({
      name: "SaathiApiError",
      status: 401,
      message: "Valid staff API credentials are required.",
    } satisfies Partial<SaathiApiError>);
  });

  it("reports backend connection failures with setup guidance", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("connection refused")));

    await expect(saathiApi.health()).rejects.toThrow("Start the API server or set SAATHI_BACKEND_URL");
  });
});
