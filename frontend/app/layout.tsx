import "./globals.css";
import "react-big-calendar/lib/css/react-big-calendar.css";
import "react-big-calendar/lib/addons/dragAndDrop/styles.css";

export const metadata = {
  title: "Dental PMS",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const themeScript = `
    (function () {
      var stored;
      try { stored = localStorage.getItem("dental_pms_theme"); } catch (e) {}
      var prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      var theme = stored === "dark" || stored === "light" ? stored : (prefersDark ? "dark" : "light");
      document.documentElement.setAttribute("data-theme", theme);
    })();
  `;
  return (
    <html lang="en" data-theme="light" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
