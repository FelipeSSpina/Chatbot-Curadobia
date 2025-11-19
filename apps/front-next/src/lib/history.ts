// file: src/lib/history.ts
// Persistência simples de histórico por usuário (ou "guest") em localStorage.

import type { DemoUser } from "./auth";

const KEY = (emailOrGuest: string) => `curadobia_chat_history__${emailOrGuest}`;

export type HistoryMsg = {
  id: string;
  role: "user" | "assistant";
  text: string;
  at: number;
};

export function loadHistory(user: DemoUser | null): HistoryMsg[] {
  try {
    const who = user?.email ?? "guest";
    const raw = localStorage.getItem(KEY(who));
    return raw ? (JSON.parse(raw) as HistoryMsg[]) : [];
  } catch {
    return [];
  }
}

export function saveHistory(user: DemoUser | null, msgs: HistoryMsg[]) {
  const who = user?.email ?? "guest";
  localStorage.setItem(KEY(who), JSON.stringify(msgs));
}

// opcional: migrar histórico de guest p/ o usuário no primeiro login (se quiser usar)
export function migrateGuestToUser(user: DemoUser) {
  const guestRaw = localStorage.getItem(KEY("guest"));
  if (!guestRaw) return;
  const userKey = KEY(user.email);
  const currentUserRaw = localStorage.getItem(userKey);
  if (!currentUserRaw) {
    localStorage.setItem(userKey, guestRaw);
  }
}
