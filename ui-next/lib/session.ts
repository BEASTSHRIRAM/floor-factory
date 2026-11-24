/* Local demo workspace session (lib/session.ts).
 *
 * The floor's sign-in is deliberately local: /login collects an email
 * + workspace name and stores them in localStorage under
 * "floor_session". There is no password, no OAuth and no server-side
 * account — the API has no user system — so nothing here pretends to
 * be one. The session exists so the console has an operator identity
 * (shown in the sidebar + profile) and a workspace name, the same
 * shape OutboundAI gets from Clerk. */

export type FloorSession = {
  email: string;
  workspace: string;
  displayName: string;
  signedInAt: string;
};

const KEY = "floor_session";

export function getSession(): FloorSession | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return null;
    const s = JSON.parse(raw) as Partial<FloorSession>;
    if (!s.email || !s.workspace) return null;
    return {
      email: String(s.email),
      workspace: String(s.workspace),
      displayName: String(s.displayName || s.email.split("@")[0] || "Operator"),
      signedInAt: String(s.signedInAt || ""),
    };
  } catch {
    return null;
  }
}

export function setSession(s: FloorSession): void {
  window.localStorage.setItem(KEY, JSON.stringify(s));
}

export function clearSession(): void {
  window.localStorage.removeItem(KEY);
}

export function operatorInitial(session: FloorSession): string {
  const src = session.displayName || session.email || "?";
  return src.trim().charAt(0).toUpperCase() || "?";
}
