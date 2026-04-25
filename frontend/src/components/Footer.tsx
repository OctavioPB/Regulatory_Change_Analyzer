export function Footer() {
  const year = new Date().getFullYear();
  return (
    <footer
      className="shrink-0 px-8 py-6 flex items-center justify-between"
      style={{ background: "var(--primary)", borderTop: "1px solid rgba(255,255,255,.08)" }}
    >
      {/* Left: monogram + name */}
      <div className="flex items-center gap-4">
        <span
          className="leading-none select-none"
          style={{ fontFamily: "'Fraunces', Georgia, serif", fontSize: "22px", fontWeight: 300 }}
        >
          <span style={{ color: "#ffffff" }}>O</span>
          <em style={{ color: "var(--gold-light)", fontStyle: "italic" }}>PB</em>
        </span>
        <div
          style={{ width: "1px", height: "28px", background: "rgba(255,255,255,.15)" }}
        />
        <div>
          <p
            style={{
              fontFamily: "'Fraunces', Georgia, serif",
              fontSize: "14px",
              fontWeight: 300,
              color: "var(--gold-light)",
              fontStyle: "italic",
              lineHeight: 1.2,
            }}
          >
            Octavio Pérez Bravo
          </p>
          <p
            className="font-body"
            style={{ fontSize: "9px", letterSpacing: "3px", textTransform: "uppercase", color: "rgba(255,255,255,.4)", marginTop: "2px" }}
          >
            Data &amp; AI Strategy Architect
          </p>
        </div>
      </div>

      {/* Center: tagline */}
      <p
        className="font-body hidden md:block"
        style={{ fontSize: "11px", color: "rgba(255,255,255,.3)", fontStyle: "italic" }}
      >
        From pipeline to decision.
      </p>

      {/* Right: product + year */}
      <div className="text-right">
        <p
          className="font-body"
          style={{ fontSize: "9px", letterSpacing: "3px", textTransform: "uppercase", color: "rgba(255,255,255,.4)" }}
        >
          Regulatory Change Analyzer
        </p>
        <p
          className="font-body"
          style={{ fontSize: "9px", color: "rgba(255,255,255,.25)", marginTop: "2px" }}
        >
          © {year} OPB · All rights reserved
        </p>
      </div>
    </footer>
  );
}
