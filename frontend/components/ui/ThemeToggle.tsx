"use client";

import { useEffect, useState } from "react";
import Icon from "./Icon";

export default function ThemeToggle({ className = "btn btn-secondary", compact = false }: {
  className?: string;
  compact?: boolean;
}) {
  const [theme, setTheme] = useState("light");
  useEffect(() => {
    setTheme(document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light");
  }, []);
  function toggle() {
    const next = theme === "light" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", next);
    try { localStorage.setItem("dental_pms_theme", next); } catch { /* Theme works without persistence. */ }
    setTheme(next);
  }
  return <button type="button" className={className} onClick={toggle} aria-label="Toggle theme"
    title={theme === "light" ? "Switch to dark mode" : "Switch to light mode"}>
    <Icon name={theme === "light" ? "moon" : "sun"} size={19} />
    {!compact && <span>{theme === "light" ? "Dark mode" : "Light mode"}</span>}
  </button>;
}
