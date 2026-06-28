import type { Metadata } from "next";
import { Code2 } from "lucide-react";
import { ComingSoon } from "../_components/coming-soon";

export const metadata: Metadata = {
  title: "IT Consulting — Coming Soon — SPS Technosoft",
  description: "SPS Technosoft IT Consulting — delivery teams and engagements from a vetted bench. Coming soon.",
};

export default function ConsultingPage() {
  return (
    <ComingSoon
      icon={Code2}
      accent="text-sps-sky"
      eyebrow="IT Consulting"
      title="Coming soon"
      blurb="Our IT consulting practice — delivery teams and engagements drawn from the same vetted bench — is launching soon. Curious about an engagement? Let's talk."
    />
  );
}
