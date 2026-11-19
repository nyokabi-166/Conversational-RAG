"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { ArrowLeft } from "lucide-react";
import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";
import { apiRequest } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await apiRequest("/auth/forgot-password", {
        method: "POST",
        body: JSON.stringify({ email: email.trim() }),
      });
      setDone(true);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "We could not send the reset email. Please try again.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-10">
      <section className="w-full max-w-md rounded-3xl border bg-card/90 p-6 shadow-lg shadow-primary/5 backdrop-blur sm:p-8">
        <Link href="/login" className="mb-8 inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Back to sign in
        </Link>
        <Logo size={44} className="mb-6" priority />
        <h1 className="text-2xl font-semibold">Forgot your password?</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Enter your account email and we will send you a link to choose a new password.
        </p>

        {done ? (
          <div role="status" className="mt-6 space-y-2 rounded-2xl border bg-muted/40 p-4 text-sm">
            <p className="font-medium">Check your email</p>
            <p className="text-muted-foreground">
              If an account exists for {email.trim()}, a reset link is on its way. It works for 30
              minutes. If you signed up with Google, use Continue with Google instead.
            </p>
          </div>
        ) : (
          <form onSubmit={submit} className="mt-6 space-y-4">
            <div className="space-y-2">
              <label htmlFor="email" className="text-sm font-medium">Email</label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="h-10 w-full rounded-xl border bg-background px-3 text-sm outline-none transition placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring/40"
              />
            </div>
            {error && <p role="alert" className="rounded-xl bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
            <Button type="submit" className="w-full" disabled={submitting}>
              {submitting ? "Sending…" : "Send reset link"}
            </Button>
          </form>
        )}
      </section>
    </main>
  );
}
