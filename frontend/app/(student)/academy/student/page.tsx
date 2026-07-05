"use client";
/* Student portal landing ("My Academy"). Placeholder home — the shell is the #3
 * deliverable; enrolment/result/pay/dashboard content arrives in #5–#7. */
import { useEffect, useState } from "react";
import { GraduationCap } from "lucide-react";
import { api } from "@/lib/api/client";

type Me = { full_name: string; college_name: string | null; course_degree: string | null };

export default function StudentHome() {
  const [me, setMe] = useState<Me | null>(null);
  useEffect(() => { api<Me>("/academy/auth/me").then(setMe).catch(() => {}); }, []);

  return (
    <div>
      <h1 className="text-3xl font-extrabold" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>
        My Academy
      </h1>
      <p className="mt-2 text-sm" style={{ color: "#6B7689" }}>
        Welcome{me ? `, ${me.full_name}` : ""}. Your entrance test, result, and enrolment will appear here.
      </p>
      <div className="mt-8 rounded-2xl bg-white p-8" style={{ border: "1px solid #EAEEF3" }}>
        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl" style={{ background: "#FBEFD7" }}>
          <GraduationCap size={22} style={{ color: "#E8A020" }} />
        </div>
        <p className="font-semibold" style={{ color: "#0A1628" }}>Your enrolment dashboard is coming soon</p>
        <p className="mt-1 text-sm" style={{ color: "#6B7689" }}>
          The entrance aptitude test, your score-based discount, payment, and enrolment status
          will live here as those surfaces are built.
        </p>
      </div>
    </div>
  );
}
