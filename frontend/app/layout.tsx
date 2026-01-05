import "./globals.css";

export const metadata = {
  title: "Dental PMS",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const themeScript = `
    (function () {
      try {
        var stored = localStorage.getItem("dental_pms_theme");
        var prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
        var theme = stored || (prefersDark ? "dark" : "light");
        document.documentElement.setAttribute("data-theme", theme);
      } catch (e) {}
    })();
  `;
  return (
    <html lang="en">
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
