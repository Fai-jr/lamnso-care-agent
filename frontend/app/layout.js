import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata = {
  title: "Muna — Lamnso Mental Health Support",
  description:
    "A confidential chatbot offering mental health support in Lamnso, the language of the Bui Division, North West Region, Cameroon.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="lns">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
