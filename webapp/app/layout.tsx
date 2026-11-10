import Link from "next/link";
import { CacheStatus } from "./CacheStatus";
import { DeleteProgress } from "./DeleteProgress";
import type { Metadata } from "next";
import "./globals.css";
import { ReviewerChip } from "./ReviewerChip";
import { ThemeToggle } from "./ThemeToggle";

export const metadata: Metadata = {
  title: "Metascience Observatory Review Platform",
};

export const dynamic = "force-dynamic";

const THEME_BOOT = `(function(){try{var t=localStorage.getItem("metascience.theme");document.documentElement.setAttribute("data-theme",t==="dark"?"dark":"light");}catch(e){document.documentElement.setAttribute("data-theme","light");}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOT }} />
      </head>
      <body>
        <div className="shell">
          <header className="topbar">
            <Link href="/" style={{ fontWeight: 600, color: "var(--fg)", display: "flex",
                                    alignItems: "center", gap: 8 }}>
              {/* Metascience Observatory globe (website public/assets/globe.svg),
                  inlined so the stroke follows the theme colour. */}
              <svg viewBox="0 0 16 16" width="22" height="22" fill="none" stroke="currentColor"
                   strokeWidth="0.9" strokeLinecap="round" aria-hidden="true">
                <circle cx="8" cy="8" r="7.35" />
                <ellipse cx="8" cy="8" rx="3" ry="7.35" />
                <ellipse cx="8" cy="8" rx="7.35" ry="3" />
              </svg>
              Metascience Observatory Review Platform
            </Link>
            <div style={{ marginLeft: "auto", display: "flex",
                          alignItems: "center", gap: 8 }}>
              <CacheStatus /><ThemeToggle />
              <ReviewerChip />
            </div>
          </header>
          <div style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column" }}>
            {children}
          </div>
        </div>
        <DeleteProgress />
      </body>
    </html>
  );
}
