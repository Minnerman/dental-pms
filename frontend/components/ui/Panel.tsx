import type { ReactNode } from "react";

type PanelProps = {
  title?: string;
  children: ReactNode;
  className?: string;
};

export default function Panel({ title, children, className }: PanelProps) {
  return (
    <section className={`panel${className ? ` ${className}` : ""}`}>
      {title && <div className="panel-title">{title}</div>}
      {children}
    </section>
  );
}
