"use client";

import Link from "next/link";

import { useMe } from "@/lib/useMe";

/** The admin pages, in the top bar for admins only (the proxy and the API
 *  refuse them to anyone else regardless). */
export function AdminLinks() {
  const { isAdmin } = useMe();
  if (!isAdmin) return null;
  return (
    <span style={{ fontSize: 12, display: "flex", gap: 10 }}>
      <Link href="/admin/users">Users</Link>
      <Link href="/admin/projects">Projects</Link>
    </span>
  );
}
