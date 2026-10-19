"use client";

import { useEffect, useState } from "react";

const KEY = "metascience.theme";

function apply(theme: "light" | "dark") {
  document.documentElement.setAttribute("data-theme", theme);
}

function SunIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="2" strokeLinecap="round"
         strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="2" strokeLinecap="round"
         strokeLinejoin="round" aria-hidden="true">
      <path d="M21 14.5A8.5 8.5 0 1 1 9.5 3 7 7 0 0 0 21 14.5z" />
    </svg>
  );
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<"light" | "dark">("light");

  useEffect(() => {
    const saved = window.localStorage.getItem(KEY);
    const next = saved === "dark" ? "dark" : "light";
    setTheme(next);
    apply(next);
  }, []);

  function toggle() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    apply(next);
    window.localStorage.setItem(KEY, next);
  }

  const toDark = theme === "light";
  return (
    <button
      type="button"
      onClick={toggle}
      title={toDark ? "Switch to dark mode" : "Switch to light mode"}
      aria-label={toDark ? "Switch to dark mode" : "Switch to light mode"}
      className="theme-toggle"
    >
      {toDark ? <MoonIcon /> : <SunIcon />}
    </button>
  );
}
