"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState, type FormEvent } from "react";
import { ArrowLeft } from "lucide-react";
import { LoadingScreen } from "@/components/loading-screen";
import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";
import { apiRequest } from "@/lib/api";

const fieldClass =
  "h-10 w-full rounded-xl border bg-background px-3 text-sm outline-none transition placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring/40";

function ResetPasswordForm() {
  const token = useSearchParams().get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    if (password.length < 8) {
      setError("Use at least 8 characters.");
      return;
    }
    if (password !== confirm) {
      setError("The two passwords do not match.");
      return;
    }
    setSubmitting(true);
    try {
      await apiRequest("/auth/reset-password", {
        method: "POST",
        body: JSON.stringify({ token, password }),
      });
      setDone(true);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "We could not change your password. Please try again.",
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
        <h1 className="text-2xl font-semibold">Choose a new password</h1>

        {!token ? (
          <div role="alert" className="mt-6 space-y-3 rounded-2xl border border-destructive/30 bg-destructive/5 p-4 text-sm">
            <p>This reset link is missing its code. Please request a new one.</p>
            <Link href="/forgot-password" className="font-medium text-primary hover:underline">Request a new link</Link>
          </div>
        ) : done ? (
          <div role="status" className="mt-6 space-y-3 rounded-2xl border bg-muted/40 p-4 text-sm">
            <p className="font-medium">Your password has been changed.</p>
            <Link href="/login" className="font-medium text-primary hover:underline">Sign in</Link>
          </div>
        ) : (
          <form onSubmit={submit} className="mt-6 space-y-4">
            <div className="space-y-2">
              <label htmlFor="new-password" className="text-sm font-medium">New password</label>
              <input id="new-password" type="password" autoComplete="new-password" required minLength={8}
                value={password} onChange={(e) => setPassword(e.target.value)} className={fieldClass} />
            </div>
            <div className="space-y-2">
              <label htmlFor="confirm-password" className="text-sm font-medium">Confirm new password</label>
              <input id="confirm-password" type="password" autoComplete="new-password" required minLength={8}
                value={confirm} onChange={(e) => setConfirm(e.target.value)} className={fieldClass} />
            </div>
            {error && (
              <p role="alert" className="rounded-xl bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {error}{" "}
                {error.includes("invalid or has expired") && (
                  <Link href="/forgot-password" className="font-medium underline">Request a new link</Link>
                )}
              </p>
            )}
            <Button type="submit" className="w-full" disabled={submitting}>
              {submitting ? "Saving…" : "Change password"}
            </Button>
          </form>
        )}
      </section>
    </main>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<LoadingScreen />}>
      <ResetPasswordForm />
    </Suspense>
  );
}
