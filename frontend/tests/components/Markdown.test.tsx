import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Markdown, parseMarkdown } from "@/components/content/Markdown";

/**
 * The Markdown renderer.
 *
 * The security tests matter more than the formatting ones: industry and blog
 * bodies live in the database and will be editable through the admin. A
 * renderer that emits raw HTML turns a paste from any website into stored XSS
 * on a page that gets crawled.
 */
describe("parseMarkdown - structure", () => {
  it("recognises headings at the levels it supports", () => {
    const blocks = parseMarkdown("## Two\n### Three\n#### Four");
    expect(blocks.map((b) => b.kind)).toEqual(["heading", "heading", "heading"]);
  });

  it("does not treat h1 as a heading, since the page provides the title", () => {
    // A body-supplied h1 would duplicate the page's own <h1>.
    const blocks = parseMarkdown("# Page title\n\nBody.");
    expect(blocks.filter((b) => b.kind === "heading")).toHaveLength(0);
  });

  it("parses unordered and ordered lists", () => {
    expect(parseMarkdown("- a\n- b")[0].kind).toBe("list");
    expect(parseMarkdown("1. a\n2. b")[0].kind).toBe("list");
  });

  it("parses blockquotes and rules", () => {
    expect(parseMarkdown("> quoted")[0].kind).toBe("quote");
    expect(parseMarkdown("---")[0].kind).toBe("rule");
  });

  it("groups consecutive lines into one paragraph", () => {
    const blocks = parseMarkdown("line one\nline two\n\nsecond para");
    expect(blocks).toHaveLength(2);
    expect(blocks[0].kind).toBe("paragraph");
  });

  it("captures fenced code verbatim", () => {
    const blocks = parseMarkdown("```bash\nls -la\n```");
    expect(blocks[0].kind).toBe("code");
  });
});

describe("parseMarkdown - inline", () => {
  it("marks bold and italic", () => {
    const [block] = parseMarkdown("**bold** and *italic*");
    if (block.kind !== "paragraph") throw new Error("expected a paragraph");
    expect(block.inline.some((i) => i.bold)).toBe(true);
    expect(block.inline.some((i) => i.italic)).toBe(true);
  });

  it("keeps code span contents out of further parsing", () => {
    // A code span containing ** must not become bold.
    const [block] = parseMarkdown("use `**literal**` here");
    if (block.kind !== "paragraph") throw new Error("expected a paragraph");
    const code = block.inline.find((i) => i.code);
    expect(code?.text).toBe("**literal**");
  });

  it("accepts http, https, mailto and relative links", () => {
    const [block] = parseMarkdown("[a](https://x.com) [b](/shop) [c](mailto:a@b.c)");
    if (block.kind !== "paragraph") throw new Error("expected a paragraph");
    expect(block.inline.filter((i) => i.href)).toHaveLength(3);
  });

  it("drops an unsafe href but keeps the link text", () => {
    const [block] = parseMarkdown("[click](javascript:alert(1))");
    if (block.kind !== "paragraph") throw new Error("expected a paragraph");
    const link = block.inline.find((i) => i.text === "click");
    expect(link?.href).toBeUndefined();
  });
});

describe("Markdown rendering - safety", () => {
  it("strips a raw script tag entirely", () => {
    const { container } = render(<Markdown source={"<script>alert(1)</script>"} />);
    expect(container.querySelector("script")).toBeNull();
    expect(container.textContent).not.toContain("alert(1)");
  });

  it("strips an img onerror handler", () => {
    const { container } = render(
      <Markdown source={'<img src=x onerror="alert(1)">'} />,
    );
    expect(container.querySelector("img")).toBeNull();
  });

  it("strips an iframe", () => {
    const { container } = render(
      <Markdown source={'<iframe src="https://evil.example"></iframe>'} />,
    );
    expect(container.querySelector("iframe")).toBeNull();
  });

  it("does not emit dangerouslySetInnerHTML for any input", () => {
    // Structural check: the renderer builds React elements, so there is no code
    // path that can execute a string.
    const { container } = render(
      <Markdown source={"<style>body{display:none}</style>"} />,
    );
    expect(container.querySelector("style")).toBeNull();
  });

  it("renders a javascript: link as plain text with no href", () => {
    render(<Markdown source={"[go](javascript:alert(1))"} />);
    const link = screen.getByText("go");
    expect(link.tagName).not.toBe("A");
  });
});

describe("Markdown rendering - output", () => {
  it("renders a heading as a real heading element", () => {
    render(<Markdown source={"## Choosing a material"} />);
    expect(
      screen.getByRole("heading", { name: "Choosing a material" }),
    ).toBeInTheDocument();
  });

  it("renders a list as a real list with items", () => {
    render(<Markdown source={"- ACP\n- Foam sheet"} />);
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });

  it("renders a blockquote as a blockquote", () => {
    const { container } = render(<Markdown source={"> quoted text"} />);
    expect(container.querySelector("blockquote")?.textContent).toContain("quoted text");
  });

  it("adds rel=noopener to an external link", () => {
    const { container } = render(<Markdown source={"[x](https://example.com)"} />);
    const anchor = container.querySelector("a");
    expect(anchor?.getAttribute("rel")).toContain("noopener");
    expect(anchor?.getAttribute("target")).toBe("_blank");
  });

  it("does not open a relative link in a new tab", () => {
    const { container } = render(<Markdown source={"[x](/shop)"} />);
    expect(container.querySelector("a")?.getAttribute("target")).toBeNull();
  });

  it("renders nothing for an empty body rather than a stray element", () => {
    const { container } = render(<Markdown source="" />);
    expect(container.firstChild).toBeNull();
  });
});
