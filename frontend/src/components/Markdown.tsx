import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * Renders model output (chat answers) as Markdown.
 *
 * Safe by construction: react-markdown never renders raw HTML from the text (no rehype-raw),
 * so `<script>` or `<img onerror>` in an answer stays literal text. Links open in a new tab
 * without opener access. Styles live under `.md` in index.css (Tailwind preflight resets
 * headings and lists).
 */
export default function Markdown({ text }: { text: string }) {
  return (
    <div className="md">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noopener noreferrer">
              {children}
            </a>
          ),
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
