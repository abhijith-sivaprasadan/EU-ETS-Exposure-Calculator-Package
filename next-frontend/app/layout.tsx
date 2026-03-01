import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "EU ETS Portfolio Studio",
  description: "Animated frontend for EU ETS CO2 + cost exposure planning",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
