import type { Metadata } from "next";
import "./globals.css";
import TrustGateNav from "../components/TrustGateNav";
import FoundryAccessGate from "../components/FoundryAccessGate";

export const metadata: Metadata = {
  title: "ZoidLab TrustGate",
  description: "AI policy engine — control what AI can access, use, and do.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="antialiased min-h-screen bg-bg text-ink">
        <TrustGateNav />
        <main className="mx-auto w-full max-w-[1320px] px-5">
          <FoundryAccessGate packageLabel="Foundry Package 06">{children}</FoundryAccessGate>
        </main>
        <footer className="mx-auto mt-20 w-full max-w-[1320px] border-t border-line px-5 py-8 text-[12px] text-faint">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span>ZoidLab TrustGate · Foundry Package 06 · Is this AI action allowed?</span>
            <span className="flex gap-4"><a href="https://foundry.zoidlab.ai" className="hover:text-dim">Foundry</a><a href="https://zoidlab.ai" className="hover:text-dim">zoidlab.ai</a></span>
          </div>
        </footer>
      </body>
    </html>
  );
}
