"use client";

import ReactMarkdown from "react-markdown";
import rehypeRaw from "rehype-raw";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";

/** Markdown as GitHub would show it: tables, and the raw HTML tables the
 *  repo READMEs use. The HTML is parsed and then sanitized (GitHub's own
 *  allow-list), so a script or an event handler in a README never runs. */
export function Markdown({ children, className }: { children: string; className?: string }) {
  return (
    <div className={`md${className ? ` ${className}` : ""}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw, rehypeSanitize]}
        components={{ a: ({ node: _node, ...props }) => <a {...props} target="_blank" rel="noreferrer" /> }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
