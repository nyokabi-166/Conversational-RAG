"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { ArrowLeft, Users } from "lucide-react";
import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import { apiRequest, type StaffAccountRecord } from "@/lib/api";

export default function StaffTeamPage() {
  const router = useRouter();
  const { user, token, ready } = useAuth();
  const [staff, setStaff] = useState<StaffAccountRecord[]>([]);
  const [username, setUsername] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [resetTarget, setResetTarget] = useState<string | null>(null);
  const [resetPassword, setResetPassword] = useState("");
  const [confirmResetPassword, setConfirmResetPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const loadStaff = useCallback(async () => {
    if (!token) return;
    try {
      setStaff(await apiRequest<StaffAccountRecord[]>("/admin/staff", {}, token));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not load staff accounts.");
    }
  }, [token]);

  useEffect(() => {
    if (ready && !user) router.replace("/staff/login");
    if (ready && user && user.role !== "super_admin") router.replace("/staff");
    if (user?.role === "super_admin") void loadStaff();
  }, [ready, user, router, loadStaff]);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setNotice(null);
    if (password !== confirmPassword) {
      setError("The passwords do not match.");
      return;
    }
    setSubmitting(true);
    try {
      await apiRequest<StaffAccountRecord>("/admin/staff", {
        method: "POST",
        body: JSON.stringify({ username, full_name: fullName || null, password }),
      }, token);
      setUsername("");
      setFullName("");
      setPassword("");
      setConfirmPassword("");
      setNotice("Staff account created. Share the username and password with the staff member privately.");
      await loadStaff();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not create the staff account.");
    } finally {
      setSubmitting(false);
    }
  };

  const resetStaffPassword = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!resetTarget) return;
    setError(null);
    setNotice(null);
    if (resetPassword !== confirmResetPassword) {
      setError("The passwords do not match.");
      return;
    }
    setSubmitting(true);
    try {
      await apiRequest<StaffAccountRecord>(`/admin/staff/${resetTarget}/password`, {
        method: "PUT",
        body: JSON.stringify({ password: resetPassword }),
      }, token);
      setResetTarget(null);
      setResetPassword("");
      setConfirmResetPassword("");
      setNotice("Staff password updated. Share the new password privately.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not update the password.");
    } finally {
      setSubmitting(false);
    }
  };

  if (!ready || !user || user.role !== "super_admin") {
    return <main className="flex min-h-screen items-center justify-center bg-muted/40 px-4"><p className="text-sm text-muted-foreground">Opening staff management…</p></main>;
  }

  return (
    <main className="min-h-screen bg-muted/40 text-foreground">
      <header className="border-b bg-background">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4 sm:px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-primary-foreground"><Users className="h-5 w-5" aria-hidden="true" /></div>
            <div><p className="font-semibold">Staff management</p><p className="text-xs text-muted-foreground">Administrator workspace</p></div>
          </div>
          <span className="text-sm text-muted-foreground">{user.full_name || user.identifier}</span>
        </div>
      </header>
      <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
        <Link href="/staff" className="mb-5 inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="h-4 w-4" aria-hidden="true" /> Staff workspace</Link>
        <h1 className="text-2xl font-semibold">Create a policy staff account</h1>
        <p className="mt-1 text-sm text-muted-foreground">Only an administrator can add staff. New accounts can sign in at the separate staff sign-in page.</p>
        <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
          <section className="rounded-xl border bg-card p-5 shadow-sm sm:p-6">
            <h2 className="font-semibold">Add staff member</h2>
            <form onSubmit={submit} className="mt-4 space-y-4">
              <div className="space-y-2"><label htmlFor="staff-name" className="text-sm font-medium">Full name</label><input id="staff-name" autoComplete="name" value={fullName} onChange={(event) => setFullName(event.target.value)} className="h-10 w-full rounded-md border bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring" /></div>
              <div className="space-y-2"><label htmlFor="staff-user" className="text-sm font-medium">Username</label><input id="staff-user" autoComplete="off" minLength={3} maxLength={100} required value={username} onChange={(event) => setUsername(event.target.value)} className="h-10 w-full rounded-md border bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring" /></div>
              <div className="space-y-2"><label htmlFor="staff-new-password" className="text-sm font-medium">Temporary password</label><input id="staff-new-password" type="password" autoComplete="new-password" minLength={12} maxLength={128} required value={password} onChange={(event) => setPassword(event.target.value)} className="h-10 w-full rounded-md border bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring" /><p className="text-xs text-muted-foreground">Use at least 12 characters and share it privately.</p></div>
              <div className="space-y-2"><label htmlFor="staff-confirm-password" className="text-sm font-medium">Confirm password</label><input id="staff-confirm-password" type="password" autoComplete="new-password" minLength={12} maxLength={128} required value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} className="h-10 w-full rounded-md border bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring" /></div>
              {error && <p role="alert" className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
              {notice && <p role="status" className="rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{notice}</p>}
              <Button type="submit" className="w-full" disabled={submitting}>{submitting ? "Creating account…" : "Create staff account"}</Button>
            </form>
          </section>
          <section className="rounded-xl border bg-card shadow-sm">
            <div className="border-b px-5 py-4 sm:px-6"><h2 className="font-semibold">Current staff accounts</h2><p className="mt-1 text-sm text-muted-foreground">Passwords are never shown here.</p></div>
            {staff.length === 0 ? <p className="px-6 py-10 text-center text-sm text-muted-foreground">No staff accounts yet.</p> : <ul className="divide-y">{staff.map((account) => <li key={account.staff_id} className="px-5 py-4 sm:px-6"><div className="flex items-center justify-between gap-4"><div><p className="font-medium">{account.full_name || account.username}</p><p className="mt-1 text-sm text-muted-foreground">@{account.username}</p></div><div className="flex items-center gap-2"><span className="rounded-full bg-muted px-2.5 py-1 text-xs font-medium">{account.role === "super_admin" ? "Administrator" : "Policy staff"}</span>{account.role === "policy_admin" && <Button type="button" variant="outline" size="sm" onClick={() => { setError(null); setResetTarget(resetTarget === account.staff_id ? null : account.staff_id); setResetPassword(""); setConfirmResetPassword(""); }}>{resetTarget === account.staff_id ? "Cancel" : "Reset password"}</Button>}</div></div>{resetTarget === account.staff_id && <form onSubmit={resetStaffPassword} className="mt-4 grid gap-3 rounded-lg bg-muted/40 p-4 sm:grid-cols-2"><div className="space-y-2"><label htmlFor={`reset-password-${account.staff_id}`} className="text-sm font-medium">New password</label><input id={`reset-password-${account.staff_id}`} type="password" autoComplete="new-password" minLength={12} maxLength={128} required value={resetPassword} onChange={(event) => setResetPassword(event.target.value)} className="h-10 w-full rounded-md border bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring" /></div><div className="space-y-2"><label htmlFor={`confirm-reset-password-${account.staff_id}`} className="text-sm font-medium">Confirm new password</label><input id={`confirm-reset-password-${account.staff_id}`} type="password" autoComplete="new-password" minLength={12} maxLength={128} required value={confirmResetPassword} onChange={(event) => setConfirmResetPassword(event.target.value)} className="h-10 w-full rounded-md border bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring" /></div><div className="sm:col-span-2"><Button type="submit" size="sm" disabled={submitting}>{submitting ? "Updating…" : "Save new password"}</Button></div></form>}</li>)}</ul>}
          </section>
        </div>
      </div>
    </main>
  );
}
