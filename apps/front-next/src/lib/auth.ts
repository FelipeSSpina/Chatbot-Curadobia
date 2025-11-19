// file: src/lib/auth.ts
// Utilitário de autenticação simples (DEMO) usando localStorage.
// ⚠️ Não use em produção: senha é "hash" base64 apenas para a demo.

export type DemoUser = {
  name: string;
  email: string;
  createdAt: number;
};

type StoredUser = DemoUser & { passB64: string };

const USERS_KEY = "curadobia_users_v1";
const CURRENT_USER_KEY = "curadobia_current_user_v1";

function loadUsers(): StoredUser[] {
  try {
    const raw = localStorage.getItem(USERS_KEY);
    return raw ? (JSON.parse(raw) as StoredUser[]) : [];
  } catch {
    return [];
  }
}
function saveUsers(users: StoredUser[]) {
  localStorage.setItem(USERS_KEY, JSON.stringify(users));
}

export function getCurrentUser(): DemoUser | null {
  try {
    const raw = localStorage.getItem(CURRENT_USER_KEY);
    return raw ? (JSON.parse(raw) as DemoUser) : null;
  } catch {
    return null;
  }
}
function setCurrentUser(user: DemoUser | null) {
  if (user) localStorage.setItem(CURRENT_USER_KEY, JSON.stringify(user));
  else localStorage.removeItem(CURRENT_USER_KEY);
}

export function logout() {
  setCurrentUser(null);
}

export function register(name: string, email: string, password: string): DemoUser {
  const users = loadUsers();
  const exists = users.some((u) => u.email.toLowerCase() === email.toLowerCase());
  if (exists) throw new Error("Já existe uma conta com este e-mail.");

  const user: StoredUser = {
    name: name.trim(),
    email: email.trim().toLowerCase(),
    createdAt: Date.now(),
    passB64: btoa(password),
  };
  users.push(user);
  saveUsers(users);

  const { passB64, ...pub } = user;
  return pub;
}

export function login(email: string, password: string): DemoUser {
  const users = loadUsers();
  const found = users.find((u) => u.email.toLowerCase() === email.toLowerCase());
  if (!found) throw new Error("E-mail não encontrado.");
  if (found.passB64 !== btoa(password)) throw new Error("Senha incorreta.");

  const { passB64, ...pub } = found;
  setCurrentUser(pub);
  return pub;
}

export function forceSetCurrentUser(user: DemoUser) {
  setCurrentUser(user);
}
