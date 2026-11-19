/**
 * Whether the server has everything @auth0/nextjs-auth0 v4 needs for Google sign-in.
 * Only names are checked here; values are never read out, logged or sent to the browser.
 */
export function auth0Configured(): boolean {
  const has = (name: string) => !!process.env[name]?.trim();
  return (
    has("AUTH0_DOMAIN") &&
    has("AUTH0_CLIENT_ID") &&
    (has("AUTH0_CLIENT_SECRET") || has("AUTH0_CLIENT_ASSERTION_SIGNING_KEY")) &&
    has("AUTH0_SECRET") &&
    has("APP_BASE_URL")
  );
}
