import type { ReactNode } from "react";

interface EyebrowProps {
  children: ReactNode;
  light?: boolean;
}

export function Eyebrow({ children, light = false }: EyebrowProps) {
  return (
    <p className={light ? "eyebrow-light" : "eyebrow"} style={{ marginBottom: 10 }}>
      {children}
    </p>
  );
}
