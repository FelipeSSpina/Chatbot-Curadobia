/* file: web/src/lib/api.ts */
const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";

export async function postChat(message: string) {
  const r = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ message, session_id: "web-session" })
  });
  if (!r.ok) throw new Error("chat failed");
  return r.json() as Promise<{ reply: string }>;
}

export async function streamChat(message: string, onToken: (t: string) => void) {
  const url = new URL(`${API_BASE}/api/stream`);
  url.searchParams.set("message", message);
  url.searchParams.set("session_id", "web-session");

  return await new Promise<void>((resolve, reject) => {
    const es = new EventSource(url.toString());
    es.onmessage = (ev) => { onToken((ev.data || "").trim()); };
    es.addEventListener("done", () => { es.close(); resolve(); });
    es.onerror = () => { es.close(); reject(new Error("sse error")); };
  });
}
