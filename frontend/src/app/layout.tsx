import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "IntelNexus Platform",
  description: "Neutral integrations- och fusionshubb för externa API-leverantörer med länk- och grafanalys, beviskedja och rapportgenerering",
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
