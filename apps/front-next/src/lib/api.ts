"use client";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export async function postChat(prompt: string): Promise<{ reply: string }> {
  const r = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt })
  });
  if (!r.ok) throw new Error(`POST /api/chat falhou: ${r.status}`);
  return r.json();
}

export async function streamChat(
  prompt: string,
  onToken: (t: string) => void
): Promise<void> {
  return new Promise((resolve, reject) => {
    const url = `${API_BASE}/api/stream?prompt=${encodeURIComponent(prompt)}`;
    const es = new EventSource(url);
    es.onmessage = (ev) => {
      const data = ev.data || "";
      if (data === "[[DONE]]") { es.close(); resolve(); return; }
      if (data) onToken(data);
    };
    es.onerror = (err) => { es.close(); reject(err); };
  });
}
