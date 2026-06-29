import { Navbar, Footer } from "./_design/site";

/** Marketing site shell — ported from the Figma design: fixed Navbar over a light
 *  (#F0F4FA) canvas, then content, then the dark Footer. (No login here — the public
 *  corporate site; the app portals live at /login, /client, /employer, etc.) */
export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col" style={{ background: "#F0F4FA", color: "#0A1628" }}>
      <Navbar />
      <main className="flex-1">{children}</main>
      <Footer />
    </div>
  );
}
