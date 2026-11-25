import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import Markdown from "./Markdown";

const html = (text: string) => renderToStaticMarkup(<Markdown text={text} />);

describe("Markdown", () => {
  it("renders the formatting models use in answers", () => {
    const out = html("### Contratos afectados\n\n* **SOFOM XYZ** [CON-4]\n* Cláusula 3.1\n\n| a | b |\n|---|---|\n| 1 | 2 |");
    expect(out).toContain("<h3>Contratos afectados</h3>");
    expect(out).toContain("<strong>SOFOM XYZ</strong> [CON-4]");
    expect(out).toContain("<li>Cláusula 3.1</li>");
    expect(out).toContain("<table>");
  });

  it("never renders raw HTML from the model", () => {
    const out = html('Hola <img src=x onerror="alert(1)"> <script>alert(2)</script>');
    expect(out).not.toContain("<img");
    expect(out).not.toContain("<script");
  });

  it("opens links in a new tab without opener access", () => {
    expect(html("[CNBV](https://www.gob.mx/cnbv)")).toContain('target="_blank" rel="noopener noreferrer"');
  });
});
