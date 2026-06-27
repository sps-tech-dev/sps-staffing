import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { Providers } from "./providers";

const sora = localFont({
  src: [
    { path: "./fonts/Sora-600.ttf", weight: "600" },
    { path: "./fonts/Sora-700.ttf", weight: "700" },
    { path: "./fonts/Sora-800.ttf", weight: "800" },
  ],
  variable: "--font-sora", display: "swap",
});
const dmSans = localFont({
  src: [
    { path: "./fonts/DMSans-400.ttf", weight: "400" },
    { path: "./fonts/DMSans-700.ttf", weight: "700" },
  ],
  variable: "--font-dm-sans", display: "swap",
});
const dmMono = localFont({
  src: [{ path: "./fonts/DMMono-400.ttf", weight: "400" }],
  variable: "--font-dm-mono", display: "swap",
});

export const metadata: Metadata = {
  title: "SPS Technosoft",
  description: "Staffing & Recruitment · IT Services · Training & EdTech",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sora.variable} ${dmSans.variable} ${dmMono.variable}`}>
      <body><Providers>{children}</Providers></body>
    </html>
  );
}
