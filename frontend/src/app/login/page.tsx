"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { ArrowLeft, MessageSquareText } from "lucide-react";
import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";

export default function LoginPage() {
  const router = useRouter();
  const { user, ready, signIn, switchAccount } = useAuth();
  const [identity, setIdentity] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const profile = await signIn("passenger", identity.trim(), password);
      router.replace(profile.role === "passenger" ? "/chat" : "/staff");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Sign in failed.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-10">
      <section className="w-full max-w-md rounded-3xl border bg-card/90 p-6 shadow-lg shadow-primary/5 backdrop-blur sm:p-8">
        <Link href="/chat" className="mb-8 inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Back to chat
        </Link>
        <div className="mb-6 flex h-11 w-11 items-center justify-center rounded-xl bg-primary text-primary-foreground">
          <MessageSquareText className="h-5 w-5" aria-hidden="true" />
        </div>
        <h1 className="text-2xl font-semibold">Passenger sign in</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Sign in to return to your saved conversations.
        </p>

        {ready && user ? (
          <div className="mt-6 space-y-3 rounded-2xl border bg-muted/40 p-4">
            <p className="text-sm">
              You’re signed in as <span className="font-medium">{user.identifier}</span>.
            </p>
            <Button
              type="button"
              className="w-full"
              onClick={() => router.replace(user.role === "passenger" ? "/chat" : "/staff")}
            >
              Continue to {user.role === "passenger" ? "Pippit" : "staff workspace"}
            </Button>
            <button
              type="button"
              onClick={() => switchAccount("/login")}
              className="w-full text-center text-sm font-medium text-primary hover:underline"
            >
              Switch account
            </button>
          </div>
        ) : (
          <>
        <a
          href="/auth/login?connection=google-oauth2&prompt=select_account&returnTo=%2Fchat"
          className="mt-6 flex h-10 w-full items-center justify-center rounded-full border bg-background px-4 text-sm font-medium transition hover:bg-accent"
        >
          <GoogleMark />
          Continue with Google
        </a>
        <div className="my-5 flex items-center gap-3 text-xs text-muted-foreground">
          <span className="h-px flex-1 bg-border" />
          or use your passenger account
          <span className="h-px flex-1 bg-border" />
        </div>

        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-2">
            <label htmlFor="identity" className="text-sm font-medium">Email</label>
            <input
              id="identity"
              type="email"
              autoComplete="email"
              required
              value={identity}
              onChange={(event) => setIdentity(event.target.value)}
              className="h-10 w-full rounded-xl border bg-background px-3 text-sm outline-none transition placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring/40"
            />
          </div>
          <div className="space-y-2">
            <label htmlFor="password" className="text-sm font-medium">Password</label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="h-10 w-full rounded-xl border bg-background px-3 text-sm outline-none transition placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring/40"
            />
          </div>
          {error && <p role="alert" className="rounded-xl bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
          <Button type="submit" className="w-full" disabled={submitting || !ready}>
            {submitting ? "Signing in…" : "Sign in"}
          </Button>
        </form>
          </>
        )}

        <p className="mt-6 text-center text-sm text-muted-foreground">
          Passenger without an account?{" "}
          <Link href="/register" className="font-medium text-primary hover:underline">Create one</Link>
        </p>
        <p className="mt-3 text-center text-sm text-muted-foreground">
          Airline staff?{" "}
          <Link href="/staff/login" className="font-medium text-primary hover:underline">Staff sign in</Link>
        </p>
      </section>
    </main>
  );
}

function GoogleMark() {
  return (
    <svg className="mr-2 h-4 w-4" viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.05 5.05 0 0 1-2.2 3.31v2.77h3.57c2.08-1.91 3.27-4.73 3.27-8.09Z" />
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.99.66-2.25 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.15v2.84A11 11 0 0 0 12 23Z" />
      <path fill="#FBBC05" d="M5.84 14.1a6.6 6.6 0 0 1 0-4.2V7.06H2.15a11 11 0 0 0 0 9.88l3.69-2.84Z" />
      <path fill="#EA4335" d="M12 4.37c1.62 0 3.07.56 4.21 1.66l3.15-3.15A10.55 10.55 0 0 0 12 1a11 11 0 0 0-9.85 6.06l3.69 2.84C6.71 7.3 9.14 4.37 12 4.37Z" />
    </svg>
  );
}
