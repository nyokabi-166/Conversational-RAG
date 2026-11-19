"use client";

import { useEffect, useState, type ReactNode } from "react";

/**
 * "Continue with Google" link that degrades gracefully: if the server reports that
 * Auth0 is not configured (or the last attempt bounced back with
 * ?google=unavailable) the button is disabled and explains why, instead of
 * sending the visitor to a failing /auth/login page.
 */
export function GoogleSignInButton({
  href,
  children,
}: {
  href: string;
  children: ReactNode;
}) {
  // null = still checking. The link stays usable meanwhile.
  const [available, setAvailable] = useState<boolean | null>(null);

  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("google") === "unavailable") {
      setAvailable(false);
      return;
    }
    let cancelled = false;
    fetch("/api/auth-config", { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : { google: false }))
      .then((data: { google?: boolean }) => {
        if (!cancelled) setAvailable(data.google === true);
      })
      .catch(() => {
        if (!cancelled) setAvailable(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const base =
    "mt-6 flex h-10 w-full items-center justify-center rounded-full border bg-background px-4 text-sm font-medium transition";

  if (available === false) {
    return (
      <div className="mt-6">
        <button
          type="button"
          disabled
          aria-disabled="true"
          className={`${base.replace("mt-6 ", "")} cursor-not-allowed opacity-50`}
        >
          {children}
        </button>
        <p role="status" className="mt-2 text-center text-xs text-muted-foreground">
          Google sign-in isn’t available right now. Please use your email and password below.
        </p>
      </div>
    );
  }

  return (
    <a href={href} className={`${base} hover:bg-accent`}>
      {children}
    </a>
  );
}
