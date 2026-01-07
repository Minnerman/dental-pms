import type { ReactNode } from "react";

type HeaderBarProps = {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
};

export default function HeaderBar({ title, subtitle, actions }: HeaderBarProps) {
  return (
    <div className="header-bar">
      <div>
        <h2 style={{ marginTop: 0 }}>{title}</h2>
        {subtitle && <p className="header-subtitle">{subtitle}</p>}
      </div>
      {actions && <div className="header-actions">{actions}</div>}
    </div>
  );
}
