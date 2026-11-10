"use client";

import useSWR from "swr";

import { getJson } from "./getJson.ts";

/** The signed-in user as the server sees them (`/api/me`). Local mode
 *  answers `role: "admin"`; while loading or on error, `me` is undefined and
 *  callers show the least-privileged view. */
export type Me = {
  mode: "local" | "hosted";
  email: string | null;
  name: string | null;
  role: "admin" | "reviewer";
  projects: string[];
};

export function useMe(): { me: Me | undefined; isAdmin: boolean } {
  const { data } = useSWR<Me>("/api/me", (url: string) => getJson<Me>(url), {
    revalidateOnFocus: false,
    shouldRetryOnError: false,
  });
  return { me: data, isAdmin: data?.role === "admin" };
}
