import Link from "next/link";
import { CompanyLogo } from "@/components/kit/company-logo";

export default function Home() {
  return (
    <main className="min-h-dvh bg-sps-navy text-white">
      <div className="mx-auto flex max-w-5xl flex-col items-center gap-8 px-6 py-28 text-center">
        <CompanyLogo size={120} />
        <h1 className="font-display text-4xl font-extrabold sm:text-6xl">
          SPS<span className="text-sps-sky">Technosoft</span>
        </h1>
        <p className="font-mono text-xs uppercase tracking-[0.3em] text-white/40">
          Staffing &amp; Recruitment · IT Services · Training &amp; EdTech
        </p>
        <div className="mt-4 flex flex-wrap justify-center gap-3">
          <Link href="/login?role=candidate" className="rounded-full bg-sps-blue px-6 py-3 text-sm font-semibold">Candidate Login</Link>
          <Link href="/login?role=client" className="rounded-full bg-white/10 px-6 py-3 text-sm font-semibold">Employer Login</Link>
          <Link href="/candidate" className="rounded-full bg-sps-gold px-6 py-3 text-sm font-semibold text-sps-navy">View Demo Dashboard</Link>
        </div>
      </div>
    </main>
  );
}
