import type { Metadata } from "next"; //Only import type to avoid unneccessary code
import { Inter } from "next/font/google";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "CSpotlight | Automated CS2 Highlights",
  description: "Extract kill and multi-kill highlights from CS2 gameplay automatically using computer vision.",
  manifest: "/site.webmanifest",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode; //Children is a built-in prop in Next.js that represents the content of the current page.
}) {
  return (
    <html lang="en" className="dark scroll-smooth">
      <body className={`${inter.className} min-h-screen bg-zinc-950 text-zinc-50 antialiased selection:bg-orange-500/30`}>
        <div 
          className="fixed inset-0 z-[-1] pointer-events-none"
          style={{
            backgroundImage: "url('/bg.png')",
            backgroundSize: "cover",
            backgroundPosition: "center",
            opacity: 0.1, 
            filter: "blur(2px)", 
          }}
        />
        <Navbar />
        <main className="pt-16">
          {children}
        </main>
        <Footer />
      </body>
    </html>
  );
}
