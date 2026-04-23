"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Props {
  text: string;
}

/**
 * Minimal markdown renderer for chat bubble content.
 *
 * Foundry (and any decent chat LLM) returns markdown by default —
 * `**bold**`, bullet lists, inline code. If we render through a raw
 * `<p>{text}</p>` the asterisks and dashes leak through as literal
 * characters, which is what prompted the v3 review's "why is the
 * chatbot returning markdown?" question.
 *
 * We deliberately don't wire in `prose` from @tailwindcss/typography —
 * that plugin isn't installed and chat bubbles don't need magazine-
 * article styling. Instead we override element defaults with tight
 * utilities that match the bubble's existing text scale.
 */
export default function ChatMarkdown({ text }: Props) {
  return (
    <div className="text-sm leading-relaxed break-words">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p className="my-1 first:mt-0 last:mb-0">{children}</p>,
          ul: ({ children }) => (
            <ul className="my-1 ml-4 list-disc space-y-0.5">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="my-1 ml-4 list-decimal space-y-0.5">{children}</ol>
          ),
          li: ({ children }) => <li className="my-0">{children}</li>,
          strong: ({ children }) => (
            <strong className="font-semibold text-foreground">{children}</strong>
          ),
          em: ({ children }) => <em className="italic">{children}</em>,
          code: ({ children }) => (
            <code className="rounded bg-muted px-1 py-0.5 text-[0.85em] font-mono">
              {children}
            </code>
          ),
          pre: ({ children }) => (
            <pre className="my-1 overflow-x-auto rounded bg-muted p-2 text-[0.85em]">
              {children}
            </pre>
          ),
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
              className="text-primary underline hover:opacity-80"
            >
              {children}
            </a>
          ),
          h1: ({ children }) => (
            <h1 className="mt-2 mb-1 text-base font-semibold">{children}</h1>
          ),
          h2: ({ children }) => (
            <h2 className="mt-2 mb-1 text-sm font-semibold">{children}</h2>
          ),
          h3: ({ children }) => (
            <h3 className="mt-1 mb-0.5 text-sm font-semibold">{children}</h3>
          ),
          hr: () => <hr className="my-2 border-muted" />,
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
