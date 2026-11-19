import { NextResponse } from "next/server";
import { auth0Configured } from "@/lib/auth0-config";

// Read at request time so changing Vercel variables and redeploying is enough.
export const dynamic = "force-dynamic";

export function GET() {
  return NextResponse.json({ google: auth0Configured() });
}
