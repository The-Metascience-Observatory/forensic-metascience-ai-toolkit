import { CacheStatus } from "./CacheStatus";
import { DeleteProgress } from "./DeleteProgress";
import type { Metadata } from "next";
import "./globals.css";
import { ReviewerChip } from "./ReviewerChip";
import { ThemeToggle } from "./ThemeToggle";

export const metadata: Metadata = {
  title: "Forensic metascience review",
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
            <a href="/" style={{ fontWeight: 600, color: "var(--fg)" }}>
              Rapid review
            </a>
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
