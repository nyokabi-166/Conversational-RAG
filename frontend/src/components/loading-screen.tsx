"use client";

import { useEffect, useState } from "react";
import { Logo } from "@/components/logo";

/**
 * Full page loading state. If it lasts more than a few seconds we explain why,
 * because the hosted backend can take up to a minute to wake up after being idle.
 */
export function LoadingScreen({ message = "Loading Pippit" }: { message?: string }) {
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => setSlow(true), 6000);
    return () => window.clearTimeout(timer);
  }, []);

  return (
    <main
      className="flex min-h-screen flex-col items-center justify-center gap-5 px-4 text-center"
      role="status"
      aria-live="polite"
    >
      <Logo size={64} priority className="animate-pulse" />
      <div className="space-y-1">
        <p className="text-base font-semibold">{message}</p>
        <p className="text-sm text-muted-foreground">
          {slow
            ? "The server is waking up after being idle. This can take up to a minute."
            : "Just a moment."}
        </p>
      </div>
      <div className="h-1.5 w-40 overflow-hidden rounded-full bg-muted">
        <div className="h-full w-1/3 animate-[pippit-slide_1.2s_ease-in-out_infinite] rounded-full bg-primary" />
      </div>
    </main>
  );
}
