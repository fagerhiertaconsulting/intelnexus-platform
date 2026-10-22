import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "OpenIntel-OSINT Platform",
  description: "Modulär plattform för insamling, länk- och grafanalys, beviskedja och rapportgenerering",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="sv" className="dark">
      <body className="bg-[#090d16] text-slate-100 antialiased min-h-screen">
        {children}
      </body>
    </html>
  );
}
