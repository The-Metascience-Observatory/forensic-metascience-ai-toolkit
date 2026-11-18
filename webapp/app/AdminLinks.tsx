"use client";

import Link from "next/link";

import { useMe } from "@/lib/useMe";

/** The admin pages, in the top bar for admins only (the proxy and the API
 *  refuse them to anyone else regardless), then everyone's own Settings. */
export function AdminLinks() {
  const { isAdmin } = useMe();
  return (
    <span style={{ fontSize: 12, display: "flex", gap: 10 }}>
      {isAdmin && <Link href="/admin/users">Users</Link>}
      {isAdmin && <Link href="/admin/projects">Projects</Link>}
      <Link href="/settings">Settings</Link>
    </span>
  );
}
