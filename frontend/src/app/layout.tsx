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

const SITE_URL = "https://madness.ubunifutech.com";

export const metadata: Metadata = {
  title: {
    default: "Ubunifu Madness — AI-Powered March Madness Predictions",
    template: "%s | Ubunifu Madness",
  },
  description:
    "March Madness bracket predictions powered by a 31-feature LR + LightGBM ensemble (0.14 Brier score). Live Elo ratings, conference strength metrics, and an AI bracket agent.",
  metadataBase: new URL(SITE_URL),
  openGraph: {
    title: "Ubunifu Madness — AI-Powered March Madness Predictions",
    description:
      "Six prediction signals blended in real time. Elo ratings, ML model, momentum, conference strength, SOS, and efficiency — with an AI agent that breaks down any matchup.",
    url: SITE_URL,
    siteName: "Ubunifu Madness",
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Ubunifu Madness — AI March Madness Predictions",
    description:
      "Six prediction signals blended in real time. Live Elo ratings for 700+ teams, blended win probabilities, and an AI bracket agent.",
  },
  robots: {
    index: true,
    follow: true,
  },
  keywords: [
    "March Madness predictions",
    "NCAA basketball",
    "Elo ratings",
    "bracket predictions",
    "AI sports analytics",
    "college basketball",
    "machine learning sports",
  ],
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
