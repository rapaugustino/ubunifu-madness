import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Ubunifu Madness — AI-Powered March Madness Predictions",
  description:
    "March Madness bracket predictions powered by a 31-feature LR + LightGBM ensemble (0.14 Brier score). Live Elo ratings, conference strength metrics, and an AI bracket agent.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <Nav />
        <main className="pt-16">
          {children}
          <Footer />
        </main>
      </body>
    </html>
  );
}
