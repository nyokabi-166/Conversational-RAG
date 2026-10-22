"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { ArrowLeft, MessageSquareText } from "lucide-react";
import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";

export default function LoginPage() {
  const router = useRouter();
  const { user, ready, signIn } = useAuth();
  const [identity, setIdentity] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (ready && user) router.replace(user.role === "passenger" ? "/" : "/staff");
  }, [ready, user, router]);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const profile = await signIn("passenger", identity.trim(), password);
      router.replace(profile.role === "passenger" ? "/" : "/staff");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Sign in failed.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted/40 px-4 py-10">
      <section className="w-full max-w-md rounded-2xl border bg-card p-6 shadow-sm sm:p-8">
        <Link href="/" className="mb-8 inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Back to chat
        </Link>
        <div className="mb-6 flex h-11 w-11 items-center justify-center rounded-xl bg-primary text-primary-foreground">
          <MessageSquareText className="h-5 w-5" aria-hidden="true" />
        </div>
        <h1 className="text-2xl font-semibold">Passenger sign in</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Sign in to return to your saved conversations.
        </p>

        <a
          href="/auth/login?connection=google-oauth2&returnTo=%2F"
          className="mt-6 flex h-10 w-full items-center justify-center rounded-md border bg-background px-4 text-sm font-medium transition hover:bg-muted"
        >
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
              className="h-10 w-full rounded-md border bg-background px-3 text-sm outline-none transition focus-visible:ring-2 focus-visible:ring-ring"
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
              className="h-10 w-full rounded-md border bg-background px-3 text-sm outline-none transition focus-visible:ring-2 focus-visible:ring-ring"
            />
          </div>
          {error && <p role="alert" className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
          <Button type="submit" className="w-full" disabled={submitting || !ready}>
            {submitting ? "Signing in…" : "Sign in"}
          </Button>
        </form>

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
