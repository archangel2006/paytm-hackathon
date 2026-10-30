import type {
  AgentAction,
  AutonomySettings,
  Handoff,
  Health,
  Merchant,
  MerchantDetail,
  Message,
  Scoreboard,
} from "./saathi-data";

const apiRoot = (process.env.NEXT_PUBLIC_SAATHI_API_URL ?? "/api").replace(/\/+$/, "");

export class SaathiApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
    this.name = "SaathiApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(`${apiRoot}${path}`, { ...init, headers });
  } catch {
    throw new SaathiApiError(
      `Cannot reach the Saathi API through ${apiRoot}. Start the API server or set SAATHI_BACKEND_URL for the frontend server.`,
    );
  }

  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const errorBody = body as { error?: { message?: string }; detail?: string } | null;
    throw new SaathiApiError(
      errorBody?.error?.message ?? errorBody?.detail ?? `Saathi API returned HTTP ${response.status}.`,
      response.status,
    );
  }
  if (body === null) {
    throw new SaathiApiError(`Saathi API returned an empty or invalid response for ${path}.`, response.status);
  }
  return body as T;
}

export const saathiApi = {
  health: () => request<Health>("/health"),
  merchants: async () => {
    type MerchantPage = { items: Merchant[]; total: number; page: number; limit: number };
    const firstPage = await request<MerchantPage>("/merchants?page=1&limit=300&sort=score");
    const pageCount = Math.ceil(firstPage.total / firstPage.limit);
    if (pageCount <= 1) return firstPage;
    const remainingPages = await Promise.all(
      Array.from({ length: pageCount - 1 }, (_, index) =>
        request<MerchantPage>(`/merchants?page=${index + 2}&limit=300&sort=score`),
      ),
    );
    return { ...firstPage, items: [firstPage, ...remainingPages].flatMap((page) => page.items) };
  },
  merchant: (id: string) => request<MerchantDetail>(`/merchants/${encodeURIComponent(id)}`),
  messages: (id: string) => request<Message[]>(`/merchants/${encodeURIComponent(id)}/messages?limit=100`),
  merchantActions: (id: string) =>
    request<AgentAction[]>(`/merchants/${encodeURIComponent(id)}/actions?limit=100`),
  actions: (status?: string) =>
    request<AgentAction[]>(`/actions?limit=200${status ? `&status=${encodeURIComponent(status)}` : ""}`),
  handoffs: () => request<Handoff[]>("/handoffs"),
  autonomy: () => request<AutonomySettings>("/autonomy"),
  scoreboard: () => request<Scoreboard>("/scoreboard"),
  sendMessage: (merchantId: string, text: string) =>
    request<{ reply: string; action: AgentAction | null; merchant_state: string }>(
      `/chat/${encodeURIComponent(merchantId)}/message`,
      { method: "POST", body: JSON.stringify({ text }) },
    ),
  uploadDocument: (merchantId: string, file: File, documentType: "pan" | "address_proof") => {
    const form = new FormData();
    form.append("file", file);
    return request<{
      document_id: string;
      quality: string;
      precheck_passed: boolean;
      issues: string[];
      reply: string;
      merchant_state: string;
    }>(`/documents/${encodeURIComponent(merchantId)}?doc_type=${documentType}`, { method: "POST", body: form });
  },
  approveAction: (id: string) =>
    request<{ status: string }>(`/actions/${encodeURIComponent(id)}/approve`, {
      method: "POST",
      body: JSON.stringify({}),
    }),
  rejectAction: (id: string) =>
    request<{ status: string }>(`/actions/${encodeURIComponent(id)}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason_code: "manager_rejected" }),
    }),
  setAutonomy: (action: string, level: string) =>
    request<{ action_type: string; level: string }>(`/autonomy/${encodeURIComponent(action)}`, {
      method: "PUT",
      body: JSON.stringify({ level }),
    }),
  resolveHandoff: (id: string, note: string) =>
    request<{ status: string }>(`/handoffs/${encodeURIComponent(id)}/resolve`, {
      method: "POST",
      body: JSON.stringify({ note }),
    }),
  runBatch: () =>
    request<{ status: string; leads_evaluated: number; newly_contacted: number; failed: number; message: string }>(
      "/agent/run-batch",
      { method: "POST" },
    ),
  recordDeviceEvent: (merchantId: string, event: "installed" | "transaction") =>
    request<{ status: string; merchant_id: string; device_status?: string; total_transactions?: number; merchant_state: string }>(
      "/demo/device-event",
      { method: "POST", body: JSON.stringify({ merchant_id: merchantId, event, count: 1 }) },
    ),
  advanceDemoClock: (hours: number) =>
    request<{ status: string; advanced_hours: number; new_clock_time: string; jobs_executed: number }>(
      "/demo/advance",
      { method: "POST", body: JSON.stringify({ hours }) },
    ),
  reset: () => request<{ status: string; message: string }>("/demo/reset", { method: "POST" }),
};
