"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { ArrowLeft, ShieldCheck } from "lucide-react";
import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import { apiRequest } from "@/lib/api";

type SetupStatus = { setup_required: boolean; setup_enabled: boolean };

export default function FirstAdminSetupPage() {
  const router = useRouter();
  const { signIn } = useAuth();
  const [status, setStatus] = useState<SetupStatus | null>(null);
  const [setupToken, setSetupToken] = useState("");
  const [username, setUsername] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    apiRequest<SetupStatus>("/auth/admin/setup-status")
      .then(setStatus)
      .catch((requestError) => {
        setError(requestError instanceof Error ? requestError.message : "Could not check setup status.");
      });
  }, []);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    if (password !== confirmPassword) {
      setError("The passwords do not match.");
      return;
    }
    setSubmitting(true);
    try {
      await apiRequest("/auth/admin/bootstrap", {
        method: "POST",
        body: JSON.stringify({
          setup_token: setupToken,
          username,
          password,
          full_name: fullName || null,
        }),
      });
      await signIn("staff", username.trim(), password);
      router.replace("/staff");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Admin setup failed.");
    } finally {
      setSubmitting(false);
    }
  };

  const setupClosed = status && !status.setup_required && !status.setup_enabled;
  const setupDisabled = status?.setup_required && !status.setup_enabled;

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted/40 px-4 py-10">
      <section className="w-full max-w-lg rounded-2xl border bg-card p-6 shadow-sm sm:p-8">
        <Link href="/staff/login" className="mb-8 inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Staff sign in
        </Link>
        <div className="mb-6 flex h-11 w-11 items-center justify-center rounded-xl bg-primary text-primary-foreground">
          <ShieldCheck className="h-5 w-5" aria-hidden="true" />
        </div>
        <h1 className="text-2xl font-semibold">
          {status && !status.setup_required ? "Recover administrator access" : "Create the first administrator"}
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          {status && !status.setup_required
            ? "Use the private recovery secret to reset the existing administrator’s password. This does not create another administrator."
            : "This one-time setup creates the administrator account. The setup secret is configured privately by the person operating the backend."}
        </p>

        {status === null ? (
          <p className="mt-6 text-sm text-muted-foreground">Checking whether first-time setup is available…</p>
        ) : setupClosed ? (
            <p className="mt-6 rounded-md bg-muted px-3 py-3 text-sm">
              An administrator account already exists, and recovery is not enabled. Sign in with that account.
            </p>
        ) : setupDisabled ? (
          <p className="mt-6 rounded-md bg-muted px-3 py-3 text-sm">
            First-time setup is not enabled yet. The backend operator must configure the setup secret before an administrator can be created.
          </p>
        ) : (
          <form onSubmit={submit} className="mt-6 space-y-4">
            <div className="space-y-2">
              <label htmlFor="setup-token" className="text-sm font-medium">One-time setup secret</label>
              <input id="setup-token" type="password" autoComplete="off" minLength={32} required value={setupToken} onChange={(event) => setSetupToken(event.target.value)} className="h-10 w-full rounded-md border bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring" />
            </div>
            <div className="space-y-2">
              <label htmlFor="admin-name" className="text-sm font-medium">Your name</label>
              <input id="admin-name" autoComplete="name" value={fullName} onChange={(event) => setFullName(event.target.value)} className="h-10 w-full rounded-md border bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring" />
            </div>
            <div className="space-y-2">
              <label htmlFor="admin-username" className="text-sm font-medium">Administrator username</label>
              <input id="admin-username" autoComplete="username" minLength={3} maxLength={100} required value={username} onChange={(event) => setUsername(event.target.value)} className="h-10 w-full rounded-md border bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring" />
            </div>
            <div className="space-y-2">
              <label htmlFor="admin-password" className="text-sm font-medium">Password</label>
              <input id="admin-password" type="password" autoComplete="new-password" minLength={12} maxLength={128} required value={password} onChange={(event) => setPassword(event.target.value)} className="h-10 w-full rounded-md border bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring" />
              <p className="text-xs text-muted-foreground">Use at least 12 characters.</p>
            </div>
            <div className="space-y-2">
              <label htmlFor="admin-confirm-password" className="text-sm font-medium">Confirm password</label>
              <input id="admin-confirm-password" type="password" autoComplete="new-password" minLength={12} maxLength={128} required value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} className="h-10 w-full rounded-md border bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring" />
            </div>
            {error && <p role="alert" className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
            <Button type="submit" className="w-full" disabled={submitting}>
              {submitting
                ? status.setup_required ? "Creating administrator…" : "Resetting administrator password…"
                : status.setup_required ? "Create administrator" : "Reset administrator password"}
            </Button>
          </form>
        )}
        {error && status === null && <p role="alert" className="mt-4 text-sm text-destructive">{error}</p>}
      </section>
    </main>
  );
}
