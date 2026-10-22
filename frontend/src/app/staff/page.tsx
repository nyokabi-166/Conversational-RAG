"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  ArrowLeft,
  CheckCircle2,
  FileText,
  LogOut,
  RefreshCw,
  ShieldCheck,
  Upload,
  Users,
  XCircle,
} from "lucide-react";
import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import {
  apiRequest,
  type DocumentRecord,
  type UploadResponse,
} from "@/lib/api";

const STAFF_ROLES = new Set(["policy_admin", "super_admin"]);
const MAX_FILES = 10;
const MAX_FILE_BYTES = 20 * 1024 * 1024;
const MAX_TOTAL_BYTES = 50 * 1024 * 1024;

function formatSize(bytes: number | null) {
  if (bytes === null) return "Size unavailable";
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export default function StaffPage() {
  const router = useRouter();
  const { user, token, ready, signOut } = useAuth();
  const [files, setFiles] = useState<File[]>([]);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [loadingDocuments, setLoadingDocuments] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadDocuments = useCallback(async () => {
    if (!token || !user || !STAFF_ROLES.has(user.role)) return;
    setLoadingDocuments(true);
    try {
      const result = await apiRequest<DocumentRecord[]>("/documents/", {}, token);
      setDocuments(result);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not load the document list.",
      );
    } finally {
      setLoadingDocuments(false);
    }
  }, [token, user]);

  useEffect(() => {
    if (ready && !user) router.replace("/staff/login");
    if (user && STAFF_ROLES.has(user.role)) void loadDocuments();
  }, [ready, user, router, loadDocuments]);

  const selectFiles = (list: FileList | null) => {
    setError(null);
    setNotice(null);
    setFiles(list ? Array.from(list) : []);
  };

  const upload = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setNotice(null);

    if (files.length === 0) {
      setError("Choose one or more PDF or HTML files first.");
      return;
    }
    if (files.length > MAX_FILES) {
      setError(`You can upload up to ${MAX_FILES} files at a time.`);
      return;
    }
    const tooLarge = files.find((file) => file.size > MAX_FILE_BYTES);
    if (tooLarge) {
      setError(`${tooLarge.name} is larger than the 20 MB per-file limit.`);
      return;
    }
    if (files.reduce((sum, file) => sum + file.size, 0) > MAX_TOTAL_BYTES) {
      setError("The combined file size must be 50 MB or smaller.");
      return;
    }

    const form = new FormData();
    files.forEach((file) => form.append("files", file));
    setUploading(true);
    try {
      const result = await apiRequest<UploadResponse>("/upload_pdfs/", {
        method: "POST",
        body: form,
      }, token);
      setNotice(
        `${result.files_indexed.length} document${result.files_indexed.length === 1 ? "" : "s"} indexed successfully.`,
      );
      setFiles([]);
      const picker = document.getElementById("policy-files") as HTMLInputElement | null;
      if (picker) picker.value = "";
      await loadDocuments();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The documents could not be uploaded.",
      );
      await loadDocuments();
    } finally {
      setUploading(false);
    }
  };

  if (!ready || !user) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-muted/40 px-4">
        <p className="text-sm text-muted-foreground">Opening staff workspace…</p>
      </main>
    );
  }

  if (!STAFF_ROLES.has(user.role)) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-muted/40 px-4">
        <section className="w-full max-w-md rounded-2xl border bg-card p-7 text-center shadow-sm">
          <ShieldCheck className="mx-auto h-8 w-8 text-muted-foreground" aria-hidden="true" />
          <h1 className="mt-4 text-xl font-semibold">Staff access required</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            This area is available to authorised policy staff only.
          </p>
          <div className="mt-5 flex justify-center gap-3">
            <Button variant="outline" onClick={() => router.push("/")}>Back to chat</Button>
            <Button onClick={() => { signOut(); router.replace("/staff/login"); }}>Sign in as staff</Button>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-muted/40 text-foreground">
      <header className="border-b bg-background">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4 sm:px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-primary-foreground">
              <ShieldCheck className="h-5 w-5" aria-hidden="true" />
            </div>
            <div>
              <p className="font-semibold">Staff workspace</p>
              <p className="text-xs text-muted-foreground">Knowledge base management</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {user.role === "super_admin" && (
              <Button variant="outline" size="sm" onClick={() => router.push("/staff/team")}>
                <Users className="h-4 w-4" aria-hidden="true" />
                <span className="ml-2">Manage staff</span>
              </Button>
            )}
            <span className="hidden text-sm text-muted-foreground sm:inline">
              {user.full_name || user.identifier}
            </span>
            <Button variant="ghost" size="sm" onClick={signOut}>
              <LogOut className="h-4 w-4" aria-hidden="true" /> Sign out
            </Button>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
        <Link href="/" className="mb-5 inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Passenger chat
        </Link>
        <div className="mb-7">
          <h1 className="text-2xl font-semibold">Policy documents</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Upload approved PDF or saved HTML sources to update the assistant’s knowledge base.
          </p>
        </div>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
          <section className="rounded-xl border bg-card p-5 shadow-sm sm:p-6">
            <div className="mb-5 flex items-start gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-muted">
                <Upload className="h-4 w-4" aria-hidden="true" />
              </div>
              <div>
                <h2 className="font-semibold">Add documents</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  PDF, HTML, or HTM · up to 10 files · 20 MB each
                </p>
              </div>
            </div>

            <form onSubmit={upload} className="space-y-4">
              <label
                htmlFor="policy-files"
                className="flex min-h-36 cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed bg-background px-5 py-6 text-center transition hover:bg-accent/50"
              >
                <Upload className="mb-2 h-5 w-5 text-muted-foreground" aria-hidden="true" />
                <span className="text-sm font-medium">Choose policy files</span>
                <span className="mt-1 text-xs text-muted-foreground">PDF, HTML, or HTM</span>
                <input
                  id="policy-files"
                  type="file"
                  accept=".pdf,.html,.htm,application/pdf,text/html"
                  multiple
                  onChange={(event) => selectFiles(event.target.files)}
                  className="sr-only"
                />
              </label>

              {files.length > 0 && (
                <ul className="space-y-2" aria-label="Selected files">
                  {files.map((file) => (
                    <li key={`${file.name}-${file.lastModified}`} className="flex items-center justify-between gap-3 rounded-md bg-muted/60 px-3 py-2 text-sm">
                      <span className="flex min-w-0 items-center gap-2 truncate">
                        <FileText className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                        <span className="truncate">{file.name}</span>
                      </span>
                      <span className="shrink-0 text-xs text-muted-foreground">{formatSize(file.size)}</span>
                    </li>
                  ))}
                </ul>
              )}

              {error && <p role="alert" className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
              {notice && <p role="status" className="rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{notice}</p>}
              <Button type="submit" className="w-full" disabled={uploading || files.length === 0}>
                {uploading ? "Uploading and indexing…" : "Upload and index"}
              </Button>
              <p className="text-xs leading-5 text-muted-foreground">
                Upload only reviewed sources. Saved webpage files do not refresh automatically when the original page changes.
              </p>
            </form>
          </section>

          <section className="rounded-xl border bg-card shadow-sm">
            <div className="flex items-center justify-between border-b px-5 py-4 sm:px-6">
              <div>
                <h2 className="font-semibold">Uploaded documents</h2>
                <p className="mt-1 text-sm text-muted-foreground">Ingestion status and upload history</p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => void loadDocuments()}
                disabled={loadingDocuments}
              >
                <RefreshCw className={`h-4 w-4 ${loadingDocuments ? "animate-spin" : ""}`} aria-hidden="true" />
                <span className="sr-only sm:not-sr-only sm:ml-2">Refresh</span>
              </Button>
            </div>
            {documents.length === 0 ? (
              <div className="px-6 py-12 text-center">
                <FileText className="mx-auto h-7 w-7 text-muted-foreground" aria-hidden="true" />
                <p className="mt-3 text-sm font-medium">No uploads recorded yet</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Documents will appear here after you upload them.
                </p>
              </div>
            ) : (
              <ul className="divide-y">
                {documents.map((item) => {
                  const succeeded = item.status === "INDEXED";
                  return (
                    <li key={item.upload_id} className="flex items-start gap-3 px-5 py-4 sm:px-6">
                      <div className="mt-0.5 text-muted-foreground">
                        <FileText className="h-4 w-4" aria-hidden="true" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="break-all text-sm font-medium">{item.filename}</p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          {formatDate(item.uploaded_at)} · {formatSize(item.file_size_bytes)}
                          {succeeded ? ` · ${item.chunk_count} chunks` : ""}
                        </p>
                      </div>
                      <span className={`inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-1 text-xs font-medium ${succeeded ? "bg-emerald-50 text-emerald-800" : "bg-destructive/10 text-destructive"}`}>
                        {succeeded ? <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" /> : <XCircle className="h-3.5 w-3.5" aria-hidden="true" />}
                        {item.status}
                      </span>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        </div>
      </div>
    </main>
  );
}
