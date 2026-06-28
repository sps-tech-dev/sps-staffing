import type { Metadata } from "next";
import { Mail, MapPin, Phone, Clock, Briefcase } from "lucide-react";
import { PageHero } from "../_components/page-hero";
import { Reveal } from "@/components/marketing/reveal";
import { CTAButton } from "@/components/marketing/ui";
import { ContactForm } from "./contact-form";

export const metadata: Metadata = {
  title: "Contact — SPS Technosoft",
  description: "Get in touch with SPS Technosoft Pvt Ltd — staffing, training, and IT consulting.",
};

const DETAILS = [
  { icon: MapPin, label: "Office", value: "Vadodara, Gujarat, India" },
  { icon: Mail, label: "Email", value: "hello@spstechnosoft.com", href: "mailto:hello@spstechnosoft.com" },
  { icon: Phone, label: "Phone", value: "+91 — coming soon" },
  { icon: Clock, label: "Hours", value: "Mon–Fri, 9:30am – 6:30pm IST" },
];

export default function ContactPage() {
  return (
    <>
      <PageHero
        eyebrow="Contact"
        title={<>Let&apos;s <span className="text-sps-sky">talk.</span></>}
        lead="Hiring, training, consulting, or just exploring — tell us what you need and we'll point you the right way."
      />

      <section className="bg-gradient-to-b from-sps-navy to-[#0a1530]">
        <div className="mx-auto grid max-w-6xl gap-10 px-6 py-24 sm:py-28 lg:grid-cols-5">
          {/* Form */}
          <div className="lg:col-span-3">
            <Reveal><ContactForm /></Reveal>
          </div>

          {/* Info panel */}
          <div className="lg:col-span-2">
            <Reveal delay={0.1}>
              <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-6 sm:p-8">
                <h2 className="font-display text-lg font-semibold text-white">Reach us directly</h2>
                <ul className="mt-6 space-y-5">
                  {DETAILS.map(({ icon: Icon, label, value, href }) => (
                    <li key={label} className="flex items-start gap-3.5">
                      <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/[0.05] ring-1 ring-white/10">
                        <Icon size={18} className="text-sps-sky" aria-hidden />
                      </span>
                      <div>
                        <div className="text-xs uppercase tracking-wide text-white/45">{label}</div>
                        {href ? (
                          <a href={href} className="text-sm text-white/85 hover:text-white">{value}</a>
                        ) : (
                          <div className="text-sm text-white/85">{value}</div>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            </Reveal>

            <Reveal delay={0.18}>
              <div className="mt-6 rounded-2xl border border-sps-blue/20 bg-sps-blue/10 p-6 sm:p-8">
                <Briefcase className="h-7 w-7 text-sps-sky" aria-hidden />
                <h3 className="mt-3 font-display text-base font-semibold text-white">Looking to hire?</h3>
                <p className="mt-2 text-sm text-white/65">
                  Jump straight into our staffing portal to post a role or sign in.
                </p>
                <div className="mt-4">
                  <CTAButton href="/staffing-and-recruitment" variant="primary">Staffing portal</CTAButton>
                </div>
              </div>
            </Reveal>
          </div>
        </div>
      </section>
    </>
  );
}
