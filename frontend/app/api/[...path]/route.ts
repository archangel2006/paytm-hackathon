function getBackendUrl(): string {
  let raw = (process.env.SAATHI_BACKEND_URL ?? "").trim();
  if (!raw) {
    raw = process.env.NODE_ENV === "production"
      ? "https://paytm-saathi-backend-i661.onrender.com"
      : "http://127.0.0.1:8000";
  }
  if (raw.startsWith("http://") || raw.startsWith("https://")) {
    return raw.replace(/\/+$/, "");
  }
  const protocol = raw.includes("localhost") || raw.includes("127.0.0.1") || !raw.includes(".") ? "http" : "https";
  return `${protocol}://${raw}`.replace(/\/+$/, "");
}

async function proxy(request: Request, path: string[]) {
  const incomingUrl = new URL(request.url);
  const backendPath = path.map((segment) => encodeURIComponent(segment)).join("/");
  const headers = new Headers();
  for (const name of ["accept", "content-type"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }

  const apiKey = process.env.SAATHI_API_KEY?.trim();
  if (apiKey) headers.set("X-API-Key", apiKey);

  const origin = request.headers.get("origin");
  if (request.method !== "GET" && origin) {
    let sameOrigin = false;
    try {
      sameOrigin = new URL(origin).origin === incomingUrl.origin;
    } catch {
      sameOrigin = false;
    }
    if (!sameOrigin) {
      return Response.json(
        { error: { code: "ORIGIN_REJECTED", message: "Cross-origin API requests are not allowed.", details: {} } },
        { status: 403 },
      );
    }
  }

  const backendUrl = getBackendUrl();
  const targetUrl = `${backendUrl}/api/${backendPath}${incomingUrl.search}`;

  try {
    const response = await fetch(targetUrl, {
      method: request.method,
      headers,
      body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer(),
      cache: "no-store",
    });
    const responseHeaders = new Headers();
    const contentType = response.headers.get("content-type");
    if (contentType) responseHeaders.set("content-type", contentType);
    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: responseHeaders,
    });
  } catch (err) {
    return Response.json(
      {
        error: {
          code: "BACKEND_UNAVAILABLE",
          message: `Cannot reach the configured Saathi backend at ${backendUrl}. Details: ${err instanceof Error ? err.message : String(err)}`,
          details: {},
        },
      },
      { status: 502 },
    );
  }
}

type RouteContext = { params: Promise<{ path: string[] }> };

export async function GET(request: Request, context: RouteContext) {
  return proxy(request, (await context.params).path);
}

export async function POST(request: Request, context: RouteContext) {
  return proxy(request, (await context.params).path);
}

export async function PUT(request: Request, context: RouteContext) {
  return proxy(request, (await context.params).path);
}
