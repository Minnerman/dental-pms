import type { SVGProps } from "react";

export type IconName =
  | "home"
  | "patients"
  | "calendar"
  | "history"
  | "wallet"
  | "reports"
  | "notes"
  | "treatment"
  | "template"
  | "settings"
  | "users"
  | "search"
  | "moon"
  | "sun"
  | "logout"
  | "menu"
  | "phone"
  | "email"
  | "copy"
  | "clinical"
  | "chart"
  | "timeline"
  | "audit";

type IconProps = Omit<SVGProps<SVGSVGElement>, "name"> & {
  name: IconName;
  size?: number;
};

export default function Icon({ name, size = 16, ...props }: IconProps) {
  const common = {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
    focusable: false,
    ...props,
  };

  switch (name) {
    case "home":
      return <svg {...common}><path d="m3 11 9-8 9 8"/><path d="M5 10v11h14V10"/><path d="M9 21v-6h6v6"/></svg>;
    case "patients":
      return <svg {...common}><circle cx="9" cy="8" r="3"/><path d="M3.5 20v-2.2A4.8 4.8 0 0 1 8.3 13h1.4a4.8 4.8 0 0 1 4.8 4.8V20"/><path d="M16 4.5a3 3 0 0 1 0 6"/><path d="M17 13a4.5 4.5 0 0 1 3.5 4.4V20"/></svg>;
    case "calendar":
      return <svg {...common}><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/></svg>;
    case "history":
      return <svg {...common}><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l3 2"/></svg>;
    case "wallet":
      return <svg {...common}><path d="M3 6.5A2.5 2.5 0 0 1 5.5 4H18a2 2 0 0 1 2 2v13H5a2 2 0 0 1-2-2Z"/><path d="M3 8h17M15 12h6v4h-6a2 2 0 0 1 0-4Z"/></svg>;
    case "reports":
      return <svg {...common}><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></svg>;
    case "notes":
      return <svg {...common}><path d="M5 3h11l3 3v15H5Z"/><path d="M15 3v4h4M8 11h8M8 15h8"/></svg>;
    case "treatment":
      return <svg {...common}><path d="M8.5 3.5c1.4 0 2.4.7 3.5.7s2.1-.7 3.5-.7c2.7 0 4.5 2.1 4 5.1-.7 4.3-2.5 11.9-5 11.9-1.2 0-1.2-4.9-2.5-4.9s-1.3 4.9-2.5 4.9c-2.5 0-4.3-7.6-5-11.9-.5-3 1.3-5.1 4-5.1Z"/></svg>;
    case "template":
      return <svg {...common}><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M9 9v11"/></svg>;
    case "settings":
      return <svg {...common}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6 1.7 1.7 0 0 0 10 3v-.2h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z"/></svg>;
    case "users":
      return <svg {...common}><circle cx="9" cy="8" r="3"/><path d="M3 20v-2a5 5 0 0 1 5-5h2a5 5 0 0 1 5 5v2M16 4.5a3 3 0 0 1 0 6M17 13a4 4 0 0 1 4 4v3"/></svg>;
    case "search":
      return <svg {...common}><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg>;
    case "moon":
      return <svg {...common}><path d="M20 15.5A8.5 8.5 0 0 1 8.5 4 8.5 8.5 0 1 0 20 15.5Z"/></svg>;
    case "sun":
      return <svg {...common}><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>;
    case "logout":
      return <svg {...common}><path d="M10 4H5v16h5M14 8l4 4-4 4M8 12h10"/></svg>;
    case "menu":
      return <svg {...common}><path d="M4 6h16M4 12h16M4 18h16"/></svg>;
    case "phone":
      return <svg {...common}><path d="M5 3h4l2 5-3 2a16 16 0 0 0 6 6l2-3 5 2v4a2 2 0 0 1-2 2C10.2 21 3 13.8 3 5a2 2 0 0 1 2-2Z"/></svg>;
    case "email":
      return <svg {...common}><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m4 7 8 6 8-6"/></svg>;
    case "copy":
      return <svg {...common}><rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/></svg>;
    case "clinical":
      return <svg {...common}><path d="M12 3v18M3 12h18"/><circle cx="12" cy="12" r="8"/></svg>;
    case "chart":
      return <svg {...common}><path d="M8.5 3.5c1.4 0 2.4.7 3.5.7s2.1-.7 3.5-.7c2.7 0 4.5 2.1 4 5.1-.7 4.3-2.5 11.9-5 11.9-1.2 0-1.2-4.9-2.5-4.9s-1.3 4.9-2.5 4.9c-2.5 0-4.3-7.6-5-11.9-.5-3 1.3-5.1 4-5.1Z"/></svg>;
    case "timeline":
      return <svg {...common}><path d="M7 4v16M7 7h10M7 12h7M7 17h10"/><circle cx="7" cy="7" r="1.5" fill="currentColor"/><circle cx="7" cy="12" r="1.5" fill="currentColor"/><circle cx="7" cy="17" r="1.5" fill="currentColor"/></svg>;
    case "audit":
      return <svg {...common}><path d="M5 3h14v18H5Z"/><path d="M8 7h8M8 11h8M8 15h5"/></svg>;
  }
}
