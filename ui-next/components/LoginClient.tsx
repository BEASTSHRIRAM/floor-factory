"use client";

/* /login — the floor's sign-in. Honest by construction: an email +
 * workspace name create a LOCAL demo session (localStorage, see
 * lib/session.ts). No password field, no fake OAuth buttons — the
 * microcopy says exactly what this is. If a session already exists,
 * entering /login goes straight to the console. */

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Mascot from "./Mascot";
import { getSession, setSession } from "../lib/session";

export default function LoginClient() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [workspace, setWorkspace] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (getSession()) router.replace("/console");
  }, [router]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const em = email.trim();
    const ws = workspace.trim();
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(em)) {
      setError("Enter a valid email address.");
      return;
    }
    if (!ws) {
      setError("Give your workspace a name — it labels your floor.");
      return;
    }
    setSession({
      email: em,
      workspace: ws,
      displayName: em.split("@")[0],
      signedInAt: new Date().toISOString(),
    });
    router.replace("/console");
  };

  return (
    <div className="flex min-h-dvh w-full items-center justify-center bg-background px-4 font-sans text-foreground">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center text-center">
          <Mascot state="idle" size={64} />
          <h1 className="mt-4 font-display text-3xl">THE FLOOR</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Sign in to enter your floor.
          </p>
        </div>

        <form
          onSubmit={submit}
          className="mt-6 space-y-3 rounded-xl border border-border bg-card p-5"
        >
          <div>
            <label htmlFor="login-email" className="mb-1 block text-sm font-medium">
              Email
            </label>
            <input
              id="login-email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label htmlFor="login-workspace" className="mb-1 block text-sm font-medium">
              Workspace name
            </label>
            <input
              id="login-workspace"
              type="text"
              value={workspace}
              onChange={(e) => setWorkspace(e.target.value)}
              placeholder="Acme Inc."
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            />
          </div>
          {error && (
            <p className="text-sm text-destructive" role="alert">
              {error}
            </p>
          )}
          <button
            type="submit"
            className="w-full rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground"
          >
            Enter the floor
          </button>
          <p className="text-center text-2xs leading-relaxed text-muted-foreground">
            Demo workspace — sign in to enter your floor. Your details
            stay in this browser (a local session); there is no account
            or password behind this demo.
          </p>
        </form>
      </div>
    </div>
  );
}
