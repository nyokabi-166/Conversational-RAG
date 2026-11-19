import { NextResponse, type NextRequest } from "next/server";
import { auth0 } from "./lib/auth0";
import { auth0Configured } from "./lib/auth0-config";

// Pages the browser navigates to while signing in or out. If Auth0 is missing or
// broken these go back to our own pages instead of showing a bare HTTP 500.
const NAVIGATION_ROUTES = new Set(["/auth/login", "/auth/callback", "/auth/logout"]);

function safeRelativePath(value: string | null): string {
  return value && value.startsWith("/") && !value.startsWith("//") ? value : "/";
}

function fallback(request: NextRequest) {
  const { pathname, searchParams } = request.nextUrl;
  if (pathname === "/auth/logout") {
    // Password-based accounts live in this app's own session storage, so signing
    // out only needs to return the person to the page they asked for.
    return NextResponse.redirect(
      new URL(safeRelativePath(searchParams.get("returnTo")), request.url),
    );
  }
  if (NAVIGATION_ROUTES.has(pathname)) {
    return NextResponse.redirect(new URL("/login?google=unavailable", request.url));
  }
  if (pathname.startsWith("/auth/")) {
    // Silent session probes (e.g. /auth/access-token) just report "not signed in".
    return NextResponse.json({ error: "auth0_unavailable" }, { status: 401 });
  }
  return NextResponse.next();
}

export async function middleware(request: NextRequest) {
  if (!auth0Configured()) return fallback(request);
  try {
    const response = await auth0.middleware(request);
    if (
      response.status >= 500 &&
      NAVIGATION_ROUTES.has(request.nextUrl.pathname)
    ) {
      return fallback(request);
    }
    return response;
  } catch (error) {
    // Log the error type only: messages from auth libraries can echo configuration.
    console.error(
      "Auth0 middleware failed:",
      error instanceof Error ? error.name : "unknown error",
    );
    return fallback(request);
  }
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt|api/auth-config).*)",
  ],
};
