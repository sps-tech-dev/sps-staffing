import { Navbar, Footer } from "./_design/site";
import { SiteWidgets } from "@/components/marketing/site-widgets";

/** Marketing site shell — ported from the Figma design: fixed Navbar over a light
 *  (#F0F4FA) canvas, then content, then the dark Footer. (No login here — the public
 *  corporate site; the app portals live at /login, /client, /employer, etc.)
 *  SiteWidgets (scroll-to-top + chat) live here so they appear on every public page
 *  but never on the portals / registration / login (those use other route groups). */
export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col" style={{ background: "#F0F4FA", color: "#0A1628" }}>
      <Navbar />
      <main className="flex-1">{children}</main>
      <Footer />
      <SiteWidgets />
    </div>
  );
}
