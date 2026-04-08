// Shared utilities for the knowledge sub-tabs:
// markdown table parsing/rendering, CSV download, source label formatting.

import React from "react";

export interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: string[];
  source_snippets?: Record<string, string>;
}

export function readableSource(src: string): string {
  if (src.startsWith("regulation::")) return src.replace("regulation::", "Regulering: ");
  if (src.startsWith("doc_")) return `Dokument ${src.replace("doc_", "")}`;
  if (src.startsWith("video_")) return `Video ${src.replace("video_", "")}`;
  if (src.startsWith("video::")) {
    const parts = src.split("::");
    return parts.length >= 2 ? `🎬 ${parts[1]}` : src;
  }
  if (src.startsWith("doc::")) {
    const parts = src.split("::");
    return parts.length >= 2 ? `📄 ${parts[1]}` : src;
  }
  return src;
}

// ── Markdown table parsing for AnalyseTab CSV downloads ──
export function extractMarkdownTables(text: string): string[][][] {
  const tableRegex = /(\|.+\|(?:\n\|[-:| ]+\|)(?:\n\|.+\|)*)/g;
  const matches = text.match(tableRegex) ?? [];
  return matches.map((tbl) => {
    const lines = tbl
      .trim()
      .split("\n")
      .filter((ln) => !/^\|[-:| ]+\|$/.test(ln.trim()));
    return lines.map((ln) =>
      ln
        .replace(/^\||\|$/g, "")
        .split("|")
        .map((c) => c.trim()),
    );
  });
}

export function tableToCsv(rows: string[][]): string {
  const escape = (s: string) => `"${s.replace(/"/g, '""')}"`;
  return rows.map((r) => r.map(escape).join(",")).join("\n");
}

export function downloadCsv(filename: string, csv: string) {
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// Render markdown text with tables shown as proper HTML <table> elements
export function renderMarkdownWithTables(text: string): React.ReactNode {
  const parts: React.ReactNode[] = [];
  const tableRegex = /(\|.+\|(?:\n\|[-:| ]+\|)(?:\n\|.+\|)*)/g;
  let lastIdx = 0;
  let match;
  let key = 0;
  while ((match = tableRegex.exec(text)) !== null) {
    if (match.index > lastIdx) {
      parts.push(
        <p key={key++} className="whitespace-pre-wrap text-sm text-[#2C3E50] leading-relaxed">
          {text.slice(lastIdx, match.index).trim()}
        </p>,
      );
    }
    const lines = match[0]
      .trim()
      .split("\n")
      .filter((ln) => !/^\|[-:| ]+\|$/.test(ln.trim()));
    const rows = lines.map((ln) =>
      ln
        .replace(/^\||\|$/g, "")
        .split("|")
        .map((c) => c.trim()),
    );
    if (rows.length >= 2) {
      parts.push(
        <div key={key++} className="overflow-x-auto my-3">
          <table className="w-full text-xs border border-[#EDE8E3]">
            <thead className="bg-[#F4F1ED]">
              <tr>
                {rows[0].map((h, i) => (
                  <th key={i} className="text-left px-2 py-1.5 font-semibold text-[#2C3E50] border-b border-[#EDE8E3]">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.slice(1).map((r, i) => (
                <tr key={i} className="border-b border-[#EDE8E3] last:border-0">
                  {r.map((c, j) => (
                    <td key={j} className="px-2 py-1.5 text-[#2C3E50]">{c}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
    }
    lastIdx = match.index + match[0].length;
  }
  if (lastIdx < text.length) {
    parts.push(
      <p key={key++} className="whitespace-pre-wrap text-sm text-[#2C3E50] leading-relaxed">
        {text.slice(lastIdx).trim()}
      </p>,
    );
  }
  return parts.length > 0 ? parts : (
    <p className="whitespace-pre-wrap text-sm text-[#2C3E50] leading-relaxed">{text}</p>
  );
}
