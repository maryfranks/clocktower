import "./lib/error-capture";

import { consumeLastCapturedError } from "./lib/error-capture";
import { renderErrorPage } from "./lib/error-page";

type ServerEntry = {
  fetch: (request: Request, env: unknown, ctx: unknown) => Promise<Response> | Response;
};

let serverEntryPromise: Promise<ServerEntry> | undefined;

async function getServerEntry(): Promise<ServerEntry> {
  if (!serverEntryPromise) {
    serverEntryPromise = import("@tanstack/react-start/server-entry").then(
      (m) => (m.default ?? m) as ServerEntry,
    );
  }
  return serverEntryPromise;
}

// h3 swallows in-handler throws into a normal 500 Response with body
// {"unhandled":true,"message":"HTTPError"} — try/catch alone never fires for those.
async function normalizeCatastrophicSsrResponse(response: Response): Promise<Response> {
  if (response.status < 500) return response;
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) return response;

  const body = await response.clone().text();
  if (!isH3SwallowedErrorBody(body)) return response;

  console.error(consumeLastCapturedError() ?? new Error(`h3 swallowed SSR error: ${body}`));
  return new Response(renderErrorPage(), {
    status: 500,
    headers: { "content-type": "text/html; charset=utf-8" },
  });
}

function isH3SwallowedErrorBody(body: string): boolean {
  try {
    const payload = JSON.parse(body) as { unhandled?: unknown; message?: unknown };
    return payload.unhandled === true && payload.message === "HTTPError";
  } catch {
    return false;
  }
}

// Hosting compresses every response at the edge. Never compress a body (gzip, brotli,
// CompressionStream) or set content-encoding here or in a server route: the body gets encoded
// twice and renders garbled.
export default {
  async fetch(request: Request, env: { SWITCHBOARD_URL?: string }, ctx: unknown) {
    try {
      const url = new URL(request.url);
      if (url.pathname.startsWith("/api/")) {
        if (!env.SWITCHBOARD_URL) {
          return new Response(JSON.stringify({ error: "SWITCHBOARD_URL is not configured" }), {
            status: 500,
            headers: { "content-type": "application/json" },
          });
        }

        const headers = new Headers();
        const contentType = request.headers.get("content-type");
        if (contentType) headers.set("content-type", contentType);
        const accept = request.headers.get("accept");
        if (accept) headers.set("accept", accept);

        const targetUrl = `${env.SWITCHBOARD_URL}${url.pathname}${url.search}`;
        const hasBody = request.method !== "GET" && request.method !== "HEAD";
        const body = hasBody ? await request.arrayBuffer() : null;

        try {
          return await fetch(targetUrl, {
            method: request.method,
            headers,
            body: body && body.byteLength > 0 ? body : null,
          });
        } catch (proxyError) {
          console.error("Proxy fetch failed:", proxyError);
          return new Response(
            JSON.stringify({
              error: proxyError instanceof Error ? proxyError.message : String(proxyError),
              targetUrl,
            }),
            {
              status: 502,
              headers: { "content-type": "application/json" },
            },
          );
        }
      }

      const handler = await getServerEntry();
      const response = await handler.fetch(request, env, ctx);
      return await normalizeCatastrophicSsrResponse(response);
    } catch (error) {
      console.error(error);
      return new Response(renderErrorPage(), {
        status: 500,
        headers: { "content-type": "text/html; charset=utf-8" },
      });
    }
  },
};
