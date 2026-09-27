import { cn } from "@/lib/cn";

/**
 * Minimal, deliberately restricted Markdown renderer.
 *
 * The seeded content is Markdown written by us, but it lives in the database
 * and is editable through the admin. Rendering it with
 * `dangerouslySetInnerHTML` after a full CommonMark pass would make every
 * stored body an XSS vector the moment an admin pastes something from a
 * website.
 *
 * So: no HTML passthrough at all. The input is split into blocks, recognised
 * structurally, and emitted as React elements. Any raw tag in the source is
 * dropped rather than escaped-and-shown, because a stray `<` in a product
 * description is a typo, not content.
 *
 * Supported: h2-h4, paragraphs, ul/ol lists, blockquote, fenced and inline
 * code, bold, italic, links (http/https and relative only), and `---` rules.
 * Not supported, by choice: images, tables, raw HTML, autolinks.
 */

type Inline = { text: string; bold?: boolean; italic?: boolean; code?: boolean; href?: string };

type Block =
  | { kind: "heading"; level: 2 | 3 | 4; inline: Inline[] }
  | { kind: "paragraph"; inline: Inline[] }
  | { kind: "list"; ordered: boolean; items: Inline[][] }
  | { kind: "quote"; inline: Inline[] }
  | { kind: "rule" }
  | { kind: "code"; text: string; language: string | null };

const SAFE_HREF = /^(https?:\/\/|\/|#|mailto:)/i;

/**
 * Elements whose *contents* must go too, not just their tags.
 *
 * Stripping only the tags would leave `alert(1)` as visible body text after a
 * `<script>` was removed, which is both a confusing artefact and a way to smuggle
 * content past a reviewer who only glances at the rendered page. These are
 * removed wholesale, contents included, before any other parsing happens.
 */
const VOID_CONTENT = /<(script|style|iframe|object|embed|noscript|template)\b[\s\S]*?<\/\1\s*>/gi;

/**
 * Strip any HTML.
 *
 * Two passes: first remove dangerous elements with their content, then remove
 * every remaining angle-bracket construct. The result can only ever be text,
 * which is what makes the rest of this module safe.
 */
function stripTags(text: string): string {
  return text.replace(VOID_CONTENT, "").replace(/<[^>]*>/g, "");
}

function parseInline(source: string): Inline[] {
  // Order matters: code spans are extracted first so their contents are never
  // re-parsed for emphasis or links.
  const parts: Inline[] = [];
  const codePattern = /`([^`]+)`/g;
  let cursor = 0;
  let match: RegExpExecArray | null;

  while ((match = codePattern.exec(source)) !== null) {
    if (match.index > cursor) {
      parts.push(...parseEmphasis(source.slice(cursor, match.index)));
    }
    parts.push({ text: match[1], code: true });
    cursor = match.index + match[0].length;
  }
  if (cursor < source.length) parts.push(...parseEmphasis(source.slice(cursor)));
  return parts;
}

function parseEmphasis(source: string): Inline[] {
  const parts: Inline[] = [];
  // Links: [label](href)
  const linkPattern = /\[([^\]]+)\]\(([^)\s]+)\)/g;
  let cursor = 0;
  let match: RegExpExecArray | null;

  while ((match = linkPattern.exec(source)) !== null) {
    if (match.index > cursor) parts.push(...parseMarks(source.slice(cursor, match.index)));
    const href = match[2];
    if (SAFE_HREF.test(href)) {
      parts.push({ text: match[1], href });
    } else {
      // Unsafe scheme, e.g. javascript:. Render the label as plain text.
      parts.push({ text: match[1] });
    }
    cursor = match.index + match[0].length;
  }
  if (cursor < source.length) parts.push(...parseMarks(source.slice(cursor)));
  return parts;
}

function parseMarks(source: string): Inline[] {
  const parts: Inline[] = [];
  const pattern = /(\*\*|__)(.+?)\1|(\*|_)(.+?)\3/g;
  let cursor = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(source)) !== null) {
    if (match.index > cursor) parts.push({ text: source.slice(cursor, match.index) });
    if (match[2] !== undefined) parts.push({ text: match[2], bold: true });
    else parts.push({ text: match[4], italic: true });
    cursor = match.index + match[0].length;
  }
  if (cursor < source.length) parts.push({ text: source.slice(cursor) });
  return parts;
}

export function parseMarkdown(source: string): Block[] {
  const lines = stripTags(source ?? "").split(/\r?\n/);
  const blocks: Block[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];

    if (line.trim().length === 0) {
      index += 1;
      continue;
    }

    // fenced code
    if (line.trimStart().startsWith("```")) {
      const language = line.trim().slice(3).trim() || null;
      const body: string[] = [];
      index += 1;
      while (index < lines.length && !lines[index].trimStart().startsWith("```")) {
        body.push(lines[index]);
        index += 1;
      }
      index += 1; // closing fence
      blocks.push({ kind: "code", text: body.join("\n"), language });
      continue;
    }

    if (/^\s*([-*_])\s*\1\s*\1[\s\S]*$/.test(line.trim()) || line.trim() === "---") {
      blocks.push({ kind: "rule" });
      index += 1;
      continue;
    }

    const heading = /^(#{2,4})\s+(.*)$/.exec(line);
    if (heading) {
      blocks.push({
        kind: "heading",
        level: heading[1].length as 2 | 3 | 4,
        inline: parseInline(heading[2]),
      });
      index += 1;
      continue;
    }

    if (/^>\s?/.test(line)) {
      const quote: string[] = [];
      while (index < lines.length && /^>\s?/.test(lines[index])) {
        quote.push(lines[index].replace(/^>\s?/, ""));
        index += 1;
      }
      blocks.push({ kind: "quote", inline: parseInline(quote.join(" ")) });
      continue;
    }

    const bullet = /^\s*[-*+]\s+(.*)$/;
    const numbered = /^\s*\d+[.)]\s+(.*)$/;
    if (bullet.test(line) || numbered.test(line)) {
      const ordered = numbered.test(line);
      const pattern = ordered ? numbered : bullet;
      const items: Inline[][] = [];
      while (index < lines.length && pattern.test(lines[index])) {
        items.push(parseInline(pattern.exec(lines[index])![1]));
        index += 1;
      }
      blocks.push({ kind: "list", ordered, items });
      continue;
    }

    // paragraph: consume until a blank line or the start of another block
    const paragraph: string[] = [];
    while (
      index < lines.length &&
      lines[index].trim().length > 0 &&
      !/^(#{2,4})\s/.test(lines[index]) &&
      !/^\s*[-*+]\s/.test(lines[index]) &&
      !/^\s*\d+[.)]\s/.test(lines[index]) &&
      !/^>\s?/.test(lines[index]) &&
      !lines[index].trimStart().startsWith("```")
    ) {
      paragraph.push(lines[index]);
      index += 1;
    }
    blocks.push({ kind: "paragraph", inline: parseInline(paragraph.join(" ")) });
  }

  return blocks;
}

function renderInline(parts: Inline[], keyPrefix: string): React.ReactNode {
  return parts.map((part, position) => {
    const key = `${keyPrefix}-${position}`;
    let node: React.ReactNode = part.text;

    if (part.code) {
      node = (
        <code key={key} className="rounded-xs bg-ink-100 px-1.5 py-0.5 font-mono text-[13px] text-ink-900">
          {part.text}
        </code>
      );
    } else if (part.href) {
      const external = /^https?:/i.test(part.href);
      node = (
        <a
          key={key}
          href={part.href}
          {...(external ? { rel: "noopener noreferrer", target: "_blank" } : {})}
          className="font-medium text-ink-900 underline decoration-signal-400 decoration-2 underline-offset-2"
        >
          {part.text}
        </a>
      );
    } else {
      if (part.bold) node = <strong className="font-semibold text-ink-950">{part.text}</strong>;
      else if (part.italic) node = <em>{part.text}</em>;
    }

    return <span key={key}>{node}</span>;
  });
}

export function Markdown({ source, className }: { source: string; className?: string }) {
  const blocks = parseMarkdown(source);

  if (blocks.length === 0) return null;

  return (
    <div className={cn("space-y-4 text-[15px] leading-relaxed text-ink-700", className)}>
      {blocks.map((block, index) => {
        const key = `block-${index}`;
        switch (block.kind) {
          case "heading": {
            const sizes = {
              2: "text-xl font-bold",
              3: "text-lg font-bold",
              4: "text-base font-semibold",
            } as const;
            const Tag = `h${block.level}` as "h2" | "h3" | "h4";
            return (
              <Tag key={key} className={cn("pt-2 text-ink-950", sizes[block.level])}>
                {renderInline(block.inline, key)}
              </Tag>
            );
          }
          case "paragraph":
            return <p key={key}>{renderInline(block.inline, key)}</p>;
          case "quote":
            return (
              <blockquote
                key={key}
                className="border-l-2 border-signal-400 bg-ink-50 py-2.5 pl-4 text-ink-800"
              >
                {renderInline(block.inline, key)}
              </blockquote>
            );
          case "rule":
            return <hr key={key} className="border-ink-200" />;
          case "code":
            return (
              <pre
                key={key}
                className="overflow-x-auto border border-ink-200 bg-ink-50 p-3.5 font-mono text-[12px] leading-relaxed text-ink-800"
              >
                <code>{block.text}</code>
              </pre>
            );
          case "list": {
            const items = block.items.map((parts, position) => (
              <li key={`${key}-${position}`} className="pl-1">
                {renderInline(parts, `${key}-${position}`)}
              </li>
            ));
            return block.ordered ? (
              <ol key={key} className="list-decimal space-y-1.5 pl-5 marker:font-semibold marker:text-ink-400">
                {items}
              </ol>
            ) : (
              <ul key={key} className="list-disc space-y-1.5 pl-5 marker:text-signal-500">
                {items}
              </ul>
            );
          }
        }
      })}
    </div>
  );
}
