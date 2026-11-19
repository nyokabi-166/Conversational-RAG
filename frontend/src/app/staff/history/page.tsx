"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ExternalLink, FileText, MessageSquareText } from "lucide-react";
import { useAuth } from "@/components/auth-provider";
import { StaffWorkspaceSidebar } from "@/components/staff-workspace-sidebar";
import {
  apiRequest,
  type HistoryDetail,
  type HistorySummary,
} from "@/lib/api";

const STAFF_ROLES = new Set(["policy_admin", "super_admin"]);

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export default function StaffHistoryPage() {
  const router = useRouter();
  const { user, token, ready } = useAuth();
  const [conversations, setConversations] = useState<HistorySummary[]>([]);
  const [selected, setSelected] = useState<HistoryDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const loadConversations = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      setConversations(
        await apiRequest<HistorySummary[]>("/history/conversations", {}, token),
      );
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not load your conversations.",
      );
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (ready && !user) router.replace("/staff/login");
    if (ready && user && !STAFF_ROLES.has(user.role)) router.replace("/staff/login");
    if (user && STAFF_ROLES.has(user.role)) void loadConversations();
  }, [ready, user, router, loadConversations]);

  const openConversation = async (conversationId: string) => {
    if (!token) return;
    setError(null);
    try {
      setSelected(
        await apiRequest<HistoryDetail>(
          `/history/conversations/${conversationId}`,
          {},
          token,
        ),
      );
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not open that conversation.",
      );
    }
  };

  if (!ready || !user || !STAFF_ROLES.has(user.role)) {
    return (
      <main className="flex min-h-screen items-center justify-center px-4">
        <p className="text-sm text-muted-foreground">Opening your conversations…</p>
      </main>
    );
  }

  return (
    <main className="min-h-screen text-foreground md:flex md:gap-4 md:p-4">
      <StaffWorkspaceSidebar active="history" />
      <div className="min-w-0 flex-1">
        <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 md:px-2">
          <h1 className="text-2xl font-semibold">Your chat history</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Conversations started with your staff account. You only ever see your own chats.
          </p>

          {error && (
            <p
              role="alert"
              className="mt-4 rounded-xl bg-destructive/10 px-3 py-2 text-sm text-destructive"
            >
              {error}
            </p>
          )}

          <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
            <section className="rounded-3xl border bg-card/90 shadow-lg shadow-primary/5 backdrop-blur">
              <div className="border-b px-5 py-4 sm:px-6">
                <h2 className="font-semibold">Conversations</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  {conversations.length} saved
                </p>
              </div>
              {loading ? (
                <p className="px-6 py-10 text-center text-sm text-muted-foreground">
                  Loading…
                </p>
              ) : conversations.length === 0 ? (
                <p className="px-6 py-10 text-center text-sm text-muted-foreground">
                  No conversations yet. Start one from the chat assistant.
                </p>
              ) : (
                <ul className="divide-y">
                  {conversations.map((conversation) => (
                    <li key={conversation.conversation_id}>
                      <button
                        type="button"
                        onClick={() => void openConversation(conversation.conversation_id)}
                        className={`w-full px-5 py-4 text-left transition-colors hover:bg-accent sm:px-6 ${
                          selected?.conversation_id === conversation.conversation_id
                            ? "bg-accent"
                            : ""
                        }`}
                      >
                        <p className="flex items-center gap-2 text-sm font-medium">
                          <MessageSquareText className="h-4 w-4 shrink-0" aria-hidden="true" />
                          <span className="truncate">
                            {conversation.last_message || "Conversation"}
                          </span>
                        </p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          {formatDate(conversation.created_at)} ·{" "}
                          {conversation.message_count} messages ·{" "}
                          {conversation.system_variant}
                        </p>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="rounded-3xl border bg-card/90 shadow-lg shadow-primary/5 backdrop-blur">
              <div className="border-b px-5 py-4 sm:px-6">
                <h2 className="font-semibold">Conversation</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  {selected
                    ? `${formatDate(selected.created_at)} · ${selected.messages.length} messages`
                    : "Choose a conversation to read it."}
                </p>
              </div>
              <div className="max-h-[70vh] space-y-4 overflow-y-auto px-5 py-5 sm:px-6">
                {!selected ? (
                  <p className="py-8 text-center text-sm text-muted-foreground">
                    Nothing open yet.
                  </p>
                ) : (
                  selected.messages.map((message) => (
                    <div
                      key={message.message_id}
                      className={`rounded-2xl px-4 py-3 text-sm leading-6 ${
                        message.role === "user"
                          ? "bg-primary text-primary-foreground"
                          : "border bg-background"
                      }`}
                    >
                      <p className="mb-1 text-xs font-medium opacity-70">
                        {message.role === "user" ? "Passenger / staff" : "Assistant"}
                      </p>
                      <p className="whitespace-pre-wrap">{message.content}</p>
                      {!!message.source_links?.length && (
                        <div className="mt-3 border-t pt-2">
                          <p className="mb-1 text-xs font-medium text-muted-foreground">
                            Sources
                          </p>
                          <ul className="space-y-1">
                            {message.source_links.map((link) => (
                              <li key={link.url} className="text-xs">
                                <a
                                  href={link.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="inline-flex items-center gap-1.5 text-primary hover:underline"
                                >
                                  <FileText className="h-3 w-3 shrink-0" aria-hidden="true" />
                                  <span className="break-words">{link.title}</span>
                                  <ExternalLink className="h-3 w-3 shrink-0" aria-hidden="true" />
                                  <span className="sr-only">(opens in a new tab)</span>
                                </a>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </section>
          </div>
        </div>
      </div>
    </main>
  );
}
