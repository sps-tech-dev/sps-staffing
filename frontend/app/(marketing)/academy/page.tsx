import type { Metadata } from "next";
import { GraduationCap } from "lucide-react";
import { ComingSoon } from "../_components/coming-soon";

export const metadata: Metadata = {
  title: "Academy / Training — Coming Soon — SPS Technosoft",
  description: "SPS Technosoft Academy — upskilling and placement-readiness programs. Coming soon.",
};

export default function AcademyPage() {
  return (
    <ComingSoon
      icon={GraduationCap}
      accent="text-sps-gold"
      eyebrow="Academy / Training"
      title="Coming soon"
      blurb="Our training academy — upskilling and placement-readiness programs that turn learners into job-ready talent — is on the way. Want early access? Get in touch."
    />
  );
}
