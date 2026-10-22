"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { ArrowLeft, ShieldCheck } from "lucide-react";
import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import { apiRequest } from "@/lib/api";

export default function StaffLoginPage() {
  const router = useRouter();
  const { user, ready, signIn } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [adminSetupAction, setAdminSetupAction] = useState<"create" | "recover" | "disabled">("disabled");

  useEffect(() => {
    if (ready && user) {
      router.replace(user.role === "passenger" ? "/" : "/staff");
    }
  }, [ready, user, router]);

  useEffect(() => {
    apiRequest<{ setup_required: boolean; setup_enabled: boolean }>(
      "/auth/admin/setup-status",
    )
      .then((status) => {
        setAdminSetupAction(
          status.setup_enabled ? (status.setup_required ? "create" : "recover") : "disabled",
        );
      })
      .catch(() => setAdminSetupAction("disabled"));
  }, []);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await signIn("staff", username.trim(), password);
      router.replace("/staff");
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Staff sign in failed.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted/40 px-4 py-10">
      <section className="w-full max-w-md rounded-2xl border bg-card p-6 shadow-sm sm:p-8">
        <Link
          href="/"
          className="mb-8 inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Back to chat
        </Link>
        <div className="mb-6 flex h-11 w-11 items-center justify-center rounded-xl bg-primary text-primary-foreground">
          <ShieldCheck className="h-5 w-5" aria-hidden="true" />
        </div>
        <h1 className="text-2xl font-semibold">Staff sign in</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Use the staff username and password provided by your administrator.
        </p>

        <form onSubmit={submit} className="mt-6 space-y-4">
          <div className="space-y-2">
            <label htmlFor="staff-username" className="text-sm font-medium">
              Staff username
            </label>
            <input
              id="staff-username"
              autoComplete="username"
              required
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              className="h-10 w-full rounded-md border bg-background px-3 text-sm outline-none transition focus-visible:ring-2 focus-visible:ring-ring"
            />
          </div>
          <div className="space-y-2">
            <label htmlFor="staff-password" className="text-sm font-medium">
              Password
            </label>
            <input
              id="staff-password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="h-10 w-full rounded-md border bg-background px-3 text-sm outline-none transition focus-visible:ring-2 focus-visible:ring-ring"
            />
          </div>
          {error && (
            <p
              role="alert"
              className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive"
            >
              {error}
            </p>
          )}
          <Button type="submit" className="w-full" disabled={submitting || !ready}>
            {submitting ? "Signing in…" : "Sign in to staff workspace"}
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-muted-foreground">
          Passenger?{" "}
          <Link href="/login" className="font-medium text-primary hover:underline">
            Passenger sign in
          </Link>
        </p>
        <p className="mt-3 text-center text-xs text-muted-foreground">
          Staff accounts are created by an administrator. There is no public staff sign-up.
        </p>
        <p className="mt-3 text-center text-sm">
          <Link href="/staff/setup" className="font-medium text-primary hover:underline">
            {adminSetupAction === "create"
              ? "Set up the first administrator"
              : adminSetupAction === "recover"
                ? "Recover administrator access"
                : "Administrator setup or recovery"}
          </Link>
        </p>
      </section>
    </main>
  );
}
