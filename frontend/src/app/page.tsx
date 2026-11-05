"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import {
  AlertTriangle,
  ArrowRight,
  ArrowUp,
  CalendarCheck,
  CheckCircle2,
  Database,
  FileCheck2,
  FileText,
  Luggage,
  MessageSquareText,
  Plane,
  RefreshCw,
  ScanSearch,
  ShieldCheck,
  Sparkles,
  Upload,
  type LucideIcon,
} from "lucide-react";
import { useAuth } from "@/components/auth-provider";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type Question = { q: string; note: string; sources: string[] };
type Topic = { id: string; label: string; icon: LucideIcon; questions: Question[] };

// Source names match the policy documents indexed in the knowledge base.
const TOPICS: Topic[] = [
  {
    id: "baggage",
    label: "Baggage",
    icon: Luggage,
    questions: [
      { q: "What is my baggage allowance?", note: "Cabin and checked allowances", sources: ["Baggage Allowance", "Hand Baggage Information"] },
      { q: "What items can’t I pack in my bags?", note: "Restricted and dangerous items", sources: ["Baggage Restrictions"] },
      { q: "How do I travel with sports or special equipment?", note: "Special baggage rules", sources: ["Special Baggage"] },
    ],
  },
  {
    id: "changes",
    label: "Changes & refunds",
    icon: RefreshCw,
    questions: [
      { q: "How can I change my booking?", note: "Rebooking and change options", sources: ["Change Booking", "Conditions of Carriage"] },
      { q: "What happens if I miss my flight?", note: "No-show and missed connections", sources: ["Conditions of Carriage"] },
      { q: "Can I get a refund on my ticket?", note: "Refund conditions", sources: ["Conditions of Carriage", "FAQs"] },
    ],
  },
  {
    id: "documents",
    label: "Travel documents",
    icon: FileCheck2,
    questions: [
      { q: "What documents do I need to travel?", note: "Passport, visa and health papers", sources: ["Visa and Health Information"] },
      { q: "Do I need a visa or health certificate for my destination?", note: "Entry requirements", sources: ["Visa and Health Information"] },
      { q: "What should I check before heading to the airport?", note: "A quick pre-flight checklist", sources: ["FAQs", "Visa and Health Information"] },
    ],
  },
  {
    id: "disruptions",
    label: "Disruptions",
    icon: AlertTriangle,
    questions: [
      { q: "What are my rights if my flight is delayed or cancelled?", note: "Delays, cancellations and care", sources: ["Conditions of Carriage"] },
      { q: "Who should I contact if something goes wrong with my trip?", note: "Getting help", sources: ["FAQs"] },
      { q: "What does the legal information say about my ticket?", note: "Terms and legal notices", sources: ["Legal Information"] },
    ],
  },
];

const STEPS = [
  { icon: MessageSquareText, title: "You ask", body: "Type a question in plain language, the way you would ask a support agent." },
  { icon: ScanSearch, title: "Pippit retrieves", body: "Your question is matched against the indexed policy documents to find the most relevant passages." },
  { icon: ShieldCheck, title: "Answers stay grounded", body: "The language model writes its reply from those passages, not from memory alone." },
  { icon: FileText, title: "Sources are shown", body: "Every answer lists the documents it drew on, so you can check it yourself." },
];

const TRIP_STEPS = [
  { icon: Plane, title: "Save your trip", body: "Add the route, dates and flight number." },
  { icon: CalendarCheck, title: "Set reminders", body: "For example: check travel documents." },
  { icon: ScanSearch, title: "Check flight status", body: "Look up a KQ flight by number and date." },
  { icon: ArrowUp, title: "Book with the airline", body: "Pippit never books, changes or cancels flights." },
];

const METRICS = [
  { name: "Faithfulness", body: "Is the answer consistent with the retrieved documents?" },
  { name: "Answer relevancy", body: "Does it address what the passenger actually asked?" },
  { name: "Context recall", body: "Did retrieval surface the passages needed to answer?" },
  { name: "Answer correctness", body: "How close is the answer to a reference answer?" },
  { name: "Consistency", body: "Does rephrasing a question change the answer? (SelfCheckGPT)" },
];

const SAMPLE_DOCS = [
  "Baggage Allowance",
  "Conditions of Carriage",
  "Visa and Health Information",
];

const panel = "rounded-3xl border bg-card/90 shadow-lg shadow-primary/5 backdrop-blur";

const NAV = [
  { href: "#topics", label: "Ask", active: true },
  { href: "#how", label: "How it works" },
  { href: "/trips", label: "Trips" },
  { href: "#staff", label: "Staff" },
  { href: "#evaluation", label: "Evaluation" },
];

function Brand() {
  return (
    <Link href="/" className="flex items-center gap-2.5" aria-label="Pippit home">
      <Image
        src="/pippit-logo.png"
        alt=""
        width={36}
        height={36}
        priority
        className="h-9 w-9 rounded-xl"
      />
      <span className="text-lg font-semibold tracking-tight">Pippit</span>
    </Link>
  );
}

function SourceChip({ name }: { name: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
      <FileText className="h-3 w-3" aria-hidden="true" />
      {name}
    </span>
  );
}

function HeroArt() {
  return (
    <div
      className="relative aspect-[44/36] w-full overflow-hidden rounded-[2rem] border bg-gradient-to-br from-secondary via-accent/70 to-background sm:aspect-[44/30]"
      aria-hidden="true"
    >
      <svg viewBox="0 0 440 300" className="absolute inset-0 h-full w-full" fill="none">
        <path
          d="M30 250 C 130 130, 280 90, 410 40"
          stroke="hsl(var(--primary))"
          strokeOpacity="0.45"
          strokeWidth="2"
          strokeDasharray="6 9"
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
        />
        <circle cx="30" cy="250" r="6" fill="hsl(var(--primary))" />
        <circle cx="30" cy="250" r="14" stroke="hsl(var(--primary))" strokeOpacity="0.25" />
      </svg>
      <Plane
        className="animate-float absolute h-10 w-10 -translate-x-1/2 -translate-y-1/2 fill-primary text-primary drop-shadow"
        style={{ left: "93%", top: "13%" }}
      />
      <div className="absolute right-4 top-4 hidden items-center gap-1.5 rounded-full border bg-card px-3 py-1.5 text-xs font-medium shadow-md sm:inline-flex">
        <CheckCircle2 className="h-3.5 w-3.5 text-primary" /> Grounded in policy documents
      </div>
      <div className="absolute bottom-4 left-4 right-4 rounded-2xl border bg-card p-3.5 shadow-xl shadow-primary/10 sm:right-auto sm:w-[80%]">
        <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
          Example conversation
        </p>
        <div className="ml-auto w-fit max-w-[90%] rounded-2xl rounded-br-md bg-primary px-3 py-2 text-xs text-primary-foreground">
          What is my baggage allowance?
        </div>
        <div className="mt-2 flex items-start gap-2">
          <Image src="/pippit-logo.png" alt="" width={24} height={24} className="mt-0.5 h-6 w-6 shrink-0 rounded-full" />
          <div className="rounded-2xl rounded-bl-md border bg-background px-3 py-2 text-xs leading-5">
            It depends on your cabin and route. Here is what the baggage policy says, with the source underneath.
            <div className="mt-1.5">
              <SourceChip name="Baggage Allowance" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function LandingPage() {
  const router = useRouter();
  const { user, ready, switchAccount } = useAuth();
  const [today, setToday] = useState("");
  const [question, setQuestion] = useState("");
  const [topicId, setTopicId] = useState(TOPICS[0].id);
  const topic = TOPICS.find((item) => item.id === topicId) ?? TOPICS[0];
  const signedIn = ready && !!user;
  const isStaff = user?.role === "policy_admin" || user?.role === "super_admin";

  useEffect(() => {
    setToday(
      new Intl.DateTimeFormat("en-GB", {
        weekday: "long",
        day: "numeric",
        month: "long",
        year: "numeric",
      }).format(new Date()),
    );
  }, []);

  const ask = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = question.trim();
    router.push(trimmed ? `/chat?q=${encodeURIComponent(trimmed)}` : "/chat");
  };

  return (
    <main className="min-h-screen px-3 py-3 text-foreground sm:px-5 sm:py-5">
      <div className="mx-auto max-w-6xl rounded-[2rem] border bg-card/60 p-3 shadow-xl shadow-primary/5 backdrop-blur sm:p-6">
        <header className="flex items-center justify-between gap-3">
          <Brand />
          <nav
            aria-label="Page sections"
            className="hidden items-center gap-1 rounded-full border bg-card px-1.5 py-1.5 shadow-sm lg:flex"
          >
            {NAV.map((item) => (
              <Link
                key={item.label}
                href={item.href}
                className={cn(
                  "rounded-full px-4 py-1.5 text-sm transition-colors",
                  item.active
                    ? "bg-foreground text-background"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground",
                )}
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            {signedIn ? (
              <div className="flex items-center gap-2">
                <span className="hidden max-w-44 truncate text-xs text-muted-foreground sm:inline" title={user?.identifier}>
                  Signed in as {user?.identifier}
                </span>
                <Link href={isStaff ? "/staff" : "/chat"} className={buttonVariants({ variant: "ink", size: "sm" })}>
                  {isStaff ? "Staff workspace" : "Open Pippit"}
                </Link>
                <button
                  type="button"
                  onClick={() => switchAccount("/login")}
                  className="px-2 text-xs text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
                >
                  Switch account
                </button>
              </div>
            ) : (
              <>
                <Link href="/login" className="px-2 text-xs text-muted-foreground hover:text-foreground sm:px-3 sm:text-sm">
                  Passenger sign in
                </Link>
                <Link href="/staff/login" className="px-2 text-xs text-muted-foreground hover:text-foreground sm:px-3 sm:text-sm">
                  Staff sign in
                </Link>
                <Link href="/chat" className={buttonVariants({ size: "sm" })}>
                  Chat now
                </Link>
              </>
            )}
          </div>
        </header>

        <section className="mt-8 grid items-center gap-8 lg:mt-10 lg:grid-cols-[1.05fr_0.95fr]">
          <div>
            <p className="min-h-4 text-xs text-muted-foreground">{today}</p>
            <h1 className="mt-3 text-4xl font-medium uppercase leading-[1.1] tracking-[0.08em] sm:text-5xl lg:text-[3.4rem]">
              Ask Pippit before you fly
            </h1>
            <p className="mt-5 max-w-xl text-base leading-7 text-muted-foreground">
              Pippit is an AI assistant for airline passengers. It answers questions on baggage, bookings and
              travel documents from verified Kenya Airways policy documents, and shows you the source of every answer.
            </p>
            <ul className="mt-6 flex flex-wrap gap-2 text-xs">
              {["No account needed to chat", "Cites its sources", "Plan trips and set reminders"].map((item) => (
                <li key={item} className="inline-flex items-center gap-1.5 rounded-full border bg-card px-3 py-1.5">
                  <CheckCircle2 className="h-3.5 w-3.5 text-primary" aria-hidden="true" /> {item}
                </li>
              ))}
            </ul>
          </div>
          <HeroArt />
        </section>

        <form onSubmit={ask} className={cn(panel, "mt-8 p-4 sm:p-5")}>
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
            <div className="inline-flex rounded-full bg-muted p-1">
              <span className="rounded-full bg-card px-3 py-1 font-medium shadow-sm">Ask Pippit</span>
              <Link href="/trips" className="rounded-full px-3 py-1 text-muted-foreground hover:text-foreground">
                Plan a trip
              </Link>
            </div>
            <p className="text-muted-foreground">Guests are welcome. Sign in only to save your history.</p>
          </div>
          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="flex-1">
              <label
                htmlFor="landing-question"
                className="text-xs font-medium uppercase tracking-wide text-muted-foreground"
              >
                Your question
              </label>
              <input
                id="landing-question"
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                maxLength={500}
                placeholder="e.g. What is my baggage allowance?"
                className="mt-1.5 h-11 w-full rounded-full border bg-background px-4 text-sm outline-none transition placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring/40"
              />
            </div>
            <button type="submit" className={cn(buttonVariants({ size: "lg" }), "w-full sm:w-auto")}>
              Ask Pippit <ArrowRight aria-hidden="true" />
            </button>
          </div>
        </form>

        <section id="topics" className="mt-8 scroll-mt-6">
          <div className="flex flex-wrap gap-2" role="group" aria-label="Question topics">
            {TOPICS.map((item) => (
              <button
                key={item.id}
                type="button"
                aria-pressed={item.id === topicId}
                onClick={() => setTopicId(item.id)}
                className={cn(
                  "inline-flex h-9 items-center gap-2 rounded-full border px-4 text-sm transition-colors",
                  item.id === topicId
                    ? "border-foreground bg-foreground text-background"
                    : "bg-card text-foreground hover:bg-accent",
                )}
              >
                <item.icon className="h-4 w-4" aria-hidden="true" />
                {item.label}
              </button>
            ))}
          </div>

          <div className="mt-4 grid gap-4 lg:grid-cols-[1.6fr_1fr]">
            <div className={cn(panel, "p-4 sm:p-6")}>
              <h2 className="text-sm font-semibold uppercase tracking-wide">{topic.label}</h2>
              <p className="mt-1 text-xs text-muted-foreground">
                Pick a question to open it in the chat. Pippit looks it up in the indexed documents listed under it.
              </p>
              <ul className="mt-2 divide-y">
                {topic.questions.map((item) => (
                  <li
                    key={item.q}
                    className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div className="flex min-w-0 items-start gap-3">
                      <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-secondary text-primary">
                        <topic.icon className="h-4 w-4" aria-hidden="true" />
                      </span>
                      <div className="min-w-0">
                        <p className="font-medium">{item.q}</p>
                        <p className="mt-0.5 text-xs text-muted-foreground">{item.note}</p>
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {item.sources.map((source) => (
                            <SourceChip key={source} name={source} />
                          ))}
                        </div>
                      </div>
                    </div>
                    <Link
                      href={`/chat?q=${encodeURIComponent(item.q)}`}
                      className={cn(buttonVariants({ variant: "ink", size: "sm" }), "self-start sm:self-center")}
                    >
                      Ask <ArrowRight aria-hidden="true" />
                    </Link>
                  </li>
                ))}
              </ul>
            </div>

            <aside className={cn(panel, "p-4 sm:p-6")} aria-labelledby="trip-preview">
              <div className="flex items-center justify-between">
                <h2 id="trip-preview" className="text-sm font-semibold uppercase tracking-wide">
                  Trip planner
                </h2>
                <span className="rounded-full bg-secondary px-2.5 py-1 text-[11px] font-medium text-primary">
                  Passengers
                </span>
              </div>
              <ol className="mt-5">
                {TRIP_STEPS.map((step, index) => (
                  <li key={step.title} className="relative flex gap-3 pb-5 last:pb-0">
                    {index < TRIP_STEPS.length - 1 && (
                      <span className="absolute left-[15px] top-8 h-[calc(100%-1.5rem)] w-px bg-border" aria-hidden="true" />
                    )}
                    <span className="relative flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
                      <step.icon className="h-4 w-4" aria-hidden="true" />
                    </span>
                    <div>
                      <p className="text-sm font-medium">{step.title}</p>
                      <p className="text-xs text-muted-foreground">{step.body}</p>
                    </div>
                  </li>
                ))}
              </ol>
              <Link
                href="/trips"
                className={cn(buttonVariants({ variant: "outline", size: "sm" }), "mt-6 w-full")}
              >
                Open the trip planner <ArrowRight aria-hidden="true" />
              </Link>
            </aside>
          </div>
        </section>

        <section id="how" className="mt-14 scroll-mt-6">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">How it works</p>
          <h2 className="mt-2 max-w-2xl text-2xl font-medium uppercase tracking-[0.06em] sm:text-3xl">
            Answers from documents, not guesses
          </h2>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">
            Pippit uses retrieval-augmented generation. Instead of relying on what a language model remembers,
            it first searches a curated library of airline policies and writes its reply from what it finds.
          </p>
          <ol className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((step, index) => (
              <li key={step.title} className={cn(panel, "p-5")}>
                <div className="flex items-center justify-between">
                  <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-secondary text-primary">
                    <step.icon className="h-5 w-5" aria-hidden="true" />
                  </span>
                  <span className="text-xs font-semibold text-muted-foreground">0{index + 1}</span>
                </div>
                <h3 className="mt-4 font-semibold">{step.title}</h3>
                <p className="mt-1 text-sm leading-6 text-muted-foreground">{step.body}</p>
              </li>
            ))}
          </ol>
          <p className="mt-4 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
            <Database className="h-3.5 w-3.5" aria-hidden="true" />
            Built with LangChain, Sentence Transformers, a Chroma vector store and a FastAPI backend.
          </p>
        </section>

        <section id="staff" className="mt-14 grid scroll-mt-6 items-center gap-6 lg:grid-cols-2">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">For airline staff</p>
            <h2 className="mt-2 text-2xl font-medium uppercase tracking-[0.06em] sm:text-3xl">
              Keep the knowledge base current
            </h2>
            <p className="mt-3 text-sm leading-6 text-muted-foreground">
              Authorised policy staff upload approved PDF or saved HTML documents. Each file is parsed, split into
              passages, embedded and indexed, and every upload is logged against the staff account that made it.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link href="/staff/login" className={buttonVariants({ variant: "ink" })}>
                <Upload aria-hidden="true" /> Staff sign in
              </Link>
              <Link href="/staff/setup" className={buttonVariants({ variant: "outline" })}>
                Administrator setup
              </Link>
            </div>
          </div>
          <div className={cn(panel, "p-4 sm:p-6")}>
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold uppercase tracking-wide">Indexed documents</h3>
              <span className="text-[11px] text-muted-foreground">Example</span>
            </div>
            <ul className="mt-3 divide-y">
              {SAMPLE_DOCS.map((name) => (
                <li key={name} className="flex items-center gap-3 py-3">
                  <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-secondary text-primary">
                    <FileText className="h-4 w-4" aria-hidden="true" />
                  </span>
                  <span className="min-w-0 flex-1 truncate text-sm font-medium">{name}</span>
                  <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-800">
                    <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" /> INDEXED
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section id="evaluation" className="mt-14 scroll-mt-6 overflow-hidden rounded-3xl bg-foreground p-6 text-background sm:p-10">
          <div className="grid gap-8 lg:grid-cols-[1fr_1.2fr]">
            <div>
              <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.2em] text-background/70">
                <Sparkles className="h-3.5 w-3.5" aria-hidden="true" /> Final Year Project
              </p>
              <h2 className="mt-3 text-2xl font-medium uppercase tracking-[0.06em] sm:text-3xl">
                Measured, not assumed
              </h2>
              <p className="mt-4 text-sm leading-6 text-background/75">
                Pippit is the subject of a research project at Strathmore University. It compares a retrieval-augmented
                chatbot against the same language model with no retrieval, using identical airline support questions,
                so any difference in quality can be attributed to grounding.
              </p>
            </div>
            <ul className="grid gap-3 sm:grid-cols-2">
              {METRICS.map((metric) => (
                <li key={metric.name} className="rounded-2xl border border-background/15 bg-background/5 p-4">
                  <p className="text-sm font-semibold">{metric.name}</p>
                  <p className="mt-1 text-xs leading-5 text-background/70">{metric.body}</p>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section className="mt-14 flex flex-col items-start justify-between gap-6 rounded-3xl bg-primary p-6 text-primary-foreground shadow-lg shadow-primary/25 sm:flex-row sm:items-center sm:p-10">
          <div>
            <h2 className="text-2xl font-medium uppercase tracking-[0.06em] sm:text-3xl">Ready when you are</h2>
            <p className="mt-2 max-w-md text-sm text-primary-foreground/85">
              Ask your first question now, or create a passenger account to keep your conversations and trips.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link href="/chat" className={buttonVariants({ variant: "secondary", size: "lg" })}>
              Chat with Pippit <ArrowRight aria-hidden="true" />
            </Link>
            <Link
              href="/register"
              className={cn(
                buttonVariants({ variant: "outline", size: "lg" }),
                "border-primary-foreground/50 bg-transparent text-primary-foreground hover:bg-primary-foreground/10 hover:text-primary-foreground",
              )}
            >
              Create account
            </Link>
          </div>
        </section>

        <footer className="mt-10 border-t pt-6 text-xs text-muted-foreground">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="space-y-2">
              <Brand />
              <p>Final Year Project, Strathmore University.</p>
            </div>
            <nav aria-label="Footer" className="flex flex-wrap gap-x-5 gap-y-2 text-sm">
              <Link href="/chat" className="hover:text-foreground">Chat</Link>
              <Link href="/trips" className="hover:text-foreground">Trips</Link>
              <Link href="/login" className="hover:text-foreground">Passenger sign in</Link>
              <Link href="/staff/login" className="hover:text-foreground">Staff sign in</Link>
            </nav>
          </div>
          <p className="mt-6 max-w-3xl leading-5">
            Pippit is an independent academic project and is not affiliated with Kenya Airways. Answers come from the
            documents currently indexed and may be out of date. Confirm fares, schedules and itinerary-specific details
            with the airline before you travel.
          </p>
        </footer>
      </div>
    </main>
  );
}
