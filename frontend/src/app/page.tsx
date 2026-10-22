"use client";

import Link from "next/link";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";
import {
  ArrowUp,
  Bot,
  Clock3,
  FileText,
  LogIn,
  LogOut,
  MessageSquareText,
  Plus,
  Plane,
  UserRound,
} from "lucide-react";
import { useAuth } from "@/components/auth-provider";
import {
  apiRequest,
  type ChatResponse,
  type HistoryDetail,
  type HistorySummary,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { AssistantMarkdown } from "@/components/assistant-markdown";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: string[];
}

const GUEST_CONVERSATION_KEY = "rag_guest_conversation_id";

function shortDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
  }).format(new Date(value));
}

export default function Home() {
  const { user, token, ready, signOut } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [history, setHistory] = useState<HistorySummary[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const loadHistory = useCallback(async () => {
    if (user?.role !== "passenger" || !token) {
      setHistory([]);
      return;
    }
    try {
      setHistory(await apiRequest<HistorySummary[]>("/history/conversations", {}, token));
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not load your conversation history.",
      );
    }
  }, [user, token]);

  useEffect(() => {
    if (!ready) return;
    if (user?.role === "passenger") {
      sessionStorage.removeItem(GUEST_CONVERSATION_KEY);
      void loadHistory();
      return;
    }
    const guestConversation = sessionStorage.getItem(GUEST_CONVERSATION_KEY);
    setConversationId(guestConversation);
  }, [ready, user, loadHistory]);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, loading]);

  const startNewConversation = () => {
    setConversationId(null);
    setMessages([]);
    setError(null);
    sessionStorage.removeItem(GUEST_CONVERSATION_KEY);
  };

  const openConversation = async (id: string) => {
    if (!token) return;
    setError(null);
    try {
      const detail = await apiRequest<HistoryDetail>(
        `/history/conversations/${encodeURIComponent(id)}`,
        {},
        token,
      );
      setConversationId(detail.conversation_id);
      setMessages(
        detail.messages
          .filter((message) => message.role === "user" || message.role === "assistant")
          .map((message) => ({
            id: message.message_id,
            role: message.role as "user" | "assistant",
            content: message.content,
            sources: Array.from(
              new Set(
                (message.retrieval_metadata || []).map((item) => item.document_source),
              ),
            ),
          })),
      );
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not open that conversation.",
      );
    }
  };

  const sendMessage = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const question = input.trim();
    if (!question || loading) return;

    setError(null);
    setInput("");
    setMessages((current) => [
      ...current,
      { id: `user-${Date.now()}`, role: "user", content: question },
    ]);
    setLoading(true);

    const form = new FormData();
    form.set("question", question);
    if (conversationId) form.set("conversation_id", conversationId);

    try {
      const passengerToken = user?.role === "passenger" ? token : null;
      const result = await apiRequest<ChatResponse>("/ask/", {
        method: "POST",
        body: form,
      }, passengerToken);
      const nextConversationId = result.conversation_id;
      setConversationId(nextConversationId);
      if (user?.role !== "passenger") {
        sessionStorage.setItem(GUEST_CONVERSATION_KEY, nextConversationId);
      }
      const sources = Array.from(
        new Set([
          ...(result.citations || []).map((citation) => citation.document_source),
          ...(result.sources || []),
        ]),
      );
      setMessages((current) => [
        ...current,
        {
          id: result.message_id || `assistant-${Date.now()}`,
          role: "assistant",
          content: result.response,
          sources,
        },
      ]);
      if (user?.role === "passenger") void loadHistory();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Your message could not be sent.",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen flex-col bg-background text-foreground md:h-screen md:flex-row">
      <aside className="flex w-full flex-col border-b bg-card md:w-72 md:border-b-0 md:border-r">
        <div className="flex items-center gap-3 px-5 py-4">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <MessageSquareText className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <p className="font-semibold leading-tight">KQ Support</p>
            <p className="text-xs text-muted-foreground">Policy assistant</p>
          </div>
        </div>

        <div className="px-4 pb-3">
          <Button className="w-full justify-start" onClick={startNewConversation}>
            <Plus aria-hidden="true" /> New conversation
          </Button>
        </div>

        {user?.role === "passenger" && (
          <section className="min-h-0 flex-1 px-3 pb-3" aria-label="Conversation history">
            <div className="flex items-center gap-2 px-2 py-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              <Clock3 className="h-3.5 w-3.5" aria-hidden="true" /> Recent conversations
            </div>
            <div className="max-h-36 space-y-1 overflow-y-auto md:max-h-none md:flex-1">
              {history.length === 0 ? (
                <p className="px-2 py-3 text-sm text-muted-foreground">
                  Your saved conversations will appear here.
                </p>
              ) : (
                history.map((item) => (
                  <button
                    key={item.conversation_id}
                    type="button"
                    onClick={() => void openConversation(item.conversation_id)}
                    className={`w-full rounded-lg px-3 py-2 text-left transition-colors hover:bg-accent ${
                      conversationId === item.conversation_id ? "bg-accent" : ""
                    }`}
                  >
                    <span className="block truncate text-sm font-medium">
                      {item.last_message || "New conversation"}
                    </span>
                    <span className="mt-1 block text-xs text-muted-foreground">
                      {shortDate(item.created_at)} · {item.message_count} messages
                    </span>
                  </button>
                ))
              )}
            </div>
          </section>
        )}

        <div className="flex items-center justify-between border-t px-4 py-3">
          {ready && user ? (
            <>
              <div className="flex min-w-0 items-center gap-2">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted">
                  <UserRound className="h-4 w-4" aria-hidden="true" />
                </div>
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">
                    {user.full_name || user.identifier}
                  </p>
                  <p className="text-xs capitalize text-muted-foreground">{user.role}</p>
                </div>
              </div>
              <Button variant="ghost" size="icon" onClick={signOut} aria-label="Sign out">
                <LogOut aria-hidden="true" />
              </Button>
            </>
          ) : (
            <div className="flex w-full items-center justify-between text-sm">
              <span className="text-muted-foreground">Using as a guest</span>
              <Link
                href="/login"
                className="inline-flex items-center gap-1 font-medium text-primary hover:underline"
              >
                <LogIn className="h-4 w-4" aria-hidden="true" /> Sign in
              </Link>
            </div>
          )}
        </div>
      </aside>

      <section className="flex min-h-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b px-5 py-3 md:px-8">
          <div>
            <h1 className="font-semibold">Passenger support</h1>
            <p className="text-xs text-muted-foreground">
              Answers grounded in the uploaded airline information
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/trips"
              className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
            >
              <Plane className="h-4 w-4" aria-hidden="true" /> Flight tools
            </Link>
            {user?.role === "policy_admin" || user?.role === "super_admin" ? (
              <Link
                href="/staff"
                className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
              >
                <FileText className="h-4 w-4" aria-hidden="true" /> Staff documents
              </Link>
            ) : null}
            {!user && ready ? (
              <>
                <Link href="/register" className="text-sm text-primary hover:underline">
                  Create account
                </Link>
                <Link href="/staff/login" className="text-sm text-muted-foreground hover:text-foreground">
                  Staff sign in
                </Link>
              </>
            ) : null}
          </div>
        </header>

        <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto px-4 py-6 md:px-8">
          <div className="mx-auto flex max-w-3xl flex-col gap-5">
            {messages.length === 0 ? (
              <div className="flex min-h-[45vh] flex-col items-center justify-center text-center">
                <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-muted text-foreground">
                  <Bot className="h-7 w-7" aria-hidden="true" />
                </div>
                <h2 className="text-xl font-semibold">How can I help with your trip?</h2>
                <p className="mt-2 max-w-md text-sm text-muted-foreground">
                  Ask about policies and travel information in the documents provided to the assistant.
                </p>
                <div className="mt-6 flex flex-wrap justify-center gap-2">
                  {["What is my baggage allowance?", "How can I change my booking?", "What documents do I need?"]
                    .map((suggestion) => (
                      <button
                        key={suggestion}
                        type="button"
                        onClick={() => setInput(suggestion)}
                        className="rounded-full border bg-card px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                      >
                        {suggestion}
                      </button>
                    ))}
                </div>
              </div>
            ) : (
              messages.map((message) => (
                <article
                  key={message.id}
                  className={`flex gap-3 ${message.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  {message.role === "assistant" && (
                    <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted">
                      <Bot className="h-4 w-4" aria-hidden="true" />
                    </div>
                  )}
                  <div
                    className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-6 md:max-w-[75%] ${
                      message.role === "user"
                        ? "bg-primary text-primary-foreground"
                        : "border bg-card"
                    }`}
                  >
                    {message.role === "assistant" ? (
                      <AssistantMarkdown content={message.content} />
                    ) : (
                      <p className="whitespace-pre-wrap">{message.content}</p>
                    )}
                    {message.role === "assistant" && !!message.sources?.length && (
                      <div className="mt-3 border-t pt-2">
                        <p className="mb-1 text-xs font-medium text-muted-foreground">Sources</p>
                        <ul className="space-y-1">
                          {message.sources.map((source) => (
                            <li key={source} className="flex items-center gap-1.5 text-xs text-muted-foreground">
                              <FileText className="h-3 w-3 shrink-0" aria-hidden="true" />
                              <span className="break-all">{source}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                  {message.role === "user" && (
                    <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
                      <UserRound className="h-4 w-4" aria-hidden="true" />
                    </div>
                  )}
                </article>
              ))
            )}
            {loading && (
              <div className="flex items-center gap-3 text-sm text-muted-foreground" role="status">
                <Bot className="h-5 w-5 animate-pulse" aria-hidden="true" />
                <span>Finding relevant information…</span>
              </div>
            )}
            {error && (
              <div role="alert" className="rounded-lg border border-destructive/40 bg-destructive/5 px-4 py-3 text-sm text-destructive">
                {error}
              </div>
            )}
          </div>
        </div>

        <div className="border-t bg-background px-4 py-4 md:px-8">
          <form onSubmit={sendMessage} className="mx-auto max-w-3xl">
            <label className="sr-only" htmlFor="chat-message">Ask a question</label>
            <div className="flex items-end gap-2 rounded-2xl border bg-card p-2 shadow-sm focus-within:ring-2 focus-within:ring-ring/40">
              <textarea
                id="chat-message"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    event.currentTarget.form?.requestSubmit();
                  }
                }}
                placeholder="Ask about baggage, bookings, or travel requirements…"
                rows={1}
                disabled={loading || !ready}
                className="max-h-36 min-h-10 flex-1 resize-y bg-transparent px-3 py-2 text-sm outline-none placeholder:text-muted-foreground disabled:opacity-60"
              />
              <Button type="submit" size="icon" disabled={!input.trim() || loading || !ready} aria-label="Send question">
                <ArrowUp aria-hidden="true" />
              </Button>
            </div>
            <p className="mt-2 text-center text-xs text-muted-foreground">
              Information is based on the documents currently indexed. Check the airline for live or itinerary-specific updates.
            </p>
          </form>
        </div>
      </section>
    </main>
  );
}
