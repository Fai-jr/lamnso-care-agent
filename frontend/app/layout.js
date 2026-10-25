import "./globals.css";

export const metadata = {
  title: "Muna: a gentle space to talk",
  description: "A calm companion for checking in on how you feel, in English and Lamnso.",
};

export const viewport = { width: "device-width", initialScale: 1, themeColor: "#E3EFE9" };

// No web fonts are downloaded: the page uses the system's rounded font, so it also works offline.
export default function RootLayout({ children }) {
  return (
    <html lang="en" data-theme="sage">
      <body>{children}</body>
    </html>
  );
}
