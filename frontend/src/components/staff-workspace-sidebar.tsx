"use client";

import Link from "next/link";
import {
  FileText,
  LogOut,
  MessageSquareText,
  Users,
  type LucideIcon,
} from "lucide-react";
import { useAuth } from "@/components/auth-provider";

type StaffPage = "chat" | "documents" | "team";

const STAFF_ROLES = new Set(["policy_admin", "super_admin"]);

export function StaffWorkspaceLinks({ active }: { active: StaffPage }) {
  const { user } = useAuth();
  if (!user || !STAFF_ROLES.has(user.role)) return null;

  const links: Array<{ page: StaffPage; href: string; label: string; icon: LucideIcon }> = [
    { page: "chat", href: "/chat", label: "Chat assistant", icon: MessageSquareText },
    { page: "documents", href: "/staff", label: "Policy documents", icon: FileText },
  ];
  if (user.role === "super_admin") {
    links.push({ page: "team", href: "/staff/team", label: "Manage staff", icon: Users });
  }

  return (
    <nav aria-label="Staff pages" className="space-y-1">
      <p className="px-3 py-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Staff workspace
      </p>
      {links.map(({ page, href, label, icon: Icon }) => (
        <Link
          key={page}
          href={href}
          aria-current={active === page ? "page" : undefined}
          className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors ${
            active === page
              ? "bg-accent font-medium text-foreground"
              : "text-muted-foreground hover:bg-accent hover:text-foreground"
          }`}
        >
          <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
          <span>{label}</span>
        </Link>
      ))}
    </nav>
  );
}

export function StaffWorkspaceSidebar({ active }: { active: StaffPage }) {
  const { user, signOut } = useAuth();
  return (
    <aside className="flex w-full shrink-0 flex-col border-b bg-card/90 px-3 py-4 backdrop-blur md:sticky md:top-4 md:h-[calc(100vh-2rem)] md:w-64 md:overflow-y-auto md:rounded-3xl md:border md:px-4 md:shadow-lg md:shadow-primary/5">
      <Link href="/chat" className="mb-5 flex items-center gap-3 px-2 py-1">
        <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-primary-foreground">
          <MessageSquareText className="h-5 w-5" aria-hidden="true" />
        </span>
        <span>
          <span className="block text-sm font-semibold">Pippit</span>
          <span className="block text-xs text-muted-foreground">Staff workspace</span>
        </span>
      </Link>
      <StaffWorkspaceLinks active={active} />
      <div className="mt-5 flex items-center justify-between border-t px-2 pt-4 md:mt-auto">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">{user?.full_name || user?.identifier}</p>
          <p className="text-xs capitalize text-muted-foreground">{user?.role?.replace("_", " ")}</p>
        </div>
        <button
          type="button"
          onClick={signOut}
          aria-label="Sign out"
          title="Sign out"
          className="rounded-full p-2 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        >
          <LogOut className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
    </aside>
  );
}
