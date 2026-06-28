"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import dynamic from "next/dynamic";
import Link from "next/link";
import { CheckCircle2, Building2 } from "lucide-react";
import { clientRegistrationSchema, type ClientRegistrationInput } from "@/lib/validation";
import { useRegistrationConfig, useRegisterClient } from "@/lib/api/hooks";
import { ApiError } from "@/lib/api/client";

const HCaptcha = dynamic(() => import("@hcaptcha/react-hcaptcha"), { ssr: false });
const TEST_SITEKEY = "10000000-ffff-ffff-ffff-000000000001";

const inputCls =
  "mt-1 w-full rounded-lg border border-cardline bg-white px-3 py-2 text-sm text-ink outline-none focus:border-[#1B5FE8]";

function Field({ label, id, error, children, hint }: {
  label: string; id: string; error?: string; hint?: string; children: React.ReactNode;
}) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-ink">{label}</label>
      {children}
      {hint && !error && <p className="mt-1 text-xs text-muted">{hint}</p>}
      {error && <p className="mt-1 text-xs text-[#DC2626]">{error}</p>}
    </div>
  );
}

export default function ClientRegisterPage() {
  const cfg = useRegistrationConfig();
  const register_ = useRegisterClient();
  const [captchaToken, setCaptchaToken] = useState<string | null>(null);
  const [captchaError, setCaptchaError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const { register, handleSubmit, formState: { errors } } = useForm<ClientRegistrationInput>({
    resolver: zodResolver(clientRegistrationSchema), mode: "onTouched",
    defaultValues: { consent_data_processing: false as unknown as true },
  });

  function onValid(data: ClientRegistrationInput) {
    setFormError(null);
    if (!captchaToken) { setCaptchaError("Please complete the captcha"); return; }
    register_.mutate({ ...data, captcha_token: captchaToken }, {
      onSuccess: () => setDone(true),
      onError: (err) => {
        const e = err as ApiError;
        setFormError(e.code === "CONSENT_REQUIRED" ? "Consent is required."
          : e.code === "CAPTCHA_FAILED" ? "Captcha failed — please retry."
          : e.message || "Registration failed — please try again.");
      },
    });
  }

  if (done) {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-page px-4">
        <div className="w-full max-w-md rounded-2xl border border-cardline bg-card p-8 text-center shadow-sm">
          <CheckCircle2 className="mx-auto mb-3 h-12 w-12 text-[#16A34A]" />
          <h1 className="text-xl font-semibold text-ink">Request received</h1>
          <p className="mt-2 text-sm text-muted">
            Thanks — your company registration is <strong>pending review</strong>. Our team will verify and
            activate your portal access, then email you to sign in. (No access is granted until approval.)
          </p>
          <Link href="/login?role=client" className="mt-6 inline-block rounded-lg bg-[#1B5FE8] px-5 py-2.5 text-sm font-semibold text-white">
            Back to login
          </Link>
        </div>
      </div>
    );
  }

  const notice = cfg.data?.notices?.data_processing;
  const sitekey = cfg.data?.hcaptcha_sitekey || TEST_SITEKEY;

  return (
    <div className="flex min-h-dvh items-center justify-center bg-page px-4 py-10">
      <div className="w-full max-w-lg rounded-2xl border border-cardline bg-card p-6 shadow-sm sm:p-8">
        <div className="mb-1 flex items-center gap-2">
          <Building2 size={20} className="text-[#1B5FE8]" />
          <h1 className="text-xl font-semibold text-ink">Register your company</h1>
        </div>
        <p className="mb-6 text-sm text-muted">Post jobs and track your hiring pipeline. We verify each company before activating access.</p>

        <form onSubmit={handleSubmit(onValid)} className="space-y-4" noValidate>
          <Field label="Company name" id="company_name" error={errors.company_name?.message}>
            <input id="company_name" autoFocus className={inputCls} placeholder="Acme Industries" {...register("company_name")} />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Industry" id="industry" error={errors.industry?.message}>
              <input id="industry" className={inputCls} placeholder="BFSI / IT / Healthcare" {...register("industry")} />
            </Field>
            <Field label="Company size" id="company_size" error={errors.company_size?.message}>
              <input id="company_size" className={inputCls} placeholder="50-200" {...register("company_size")} />
            </Field>
          </div>
          <Field label="Contact person" id="contact_person" error={errors.contact_person?.message}>
            <input id="contact_person" className={inputCls} placeholder="Rohan Mehta" {...register("contact_person")} />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Work email" id="email" error={errors.email?.message}>
              <input id="email" type="email" autoComplete="email" className={inputCls} placeholder="name@company.com" {...register("email")} />
            </Field>
            <Field label="Phone" id="phone" error={errors.phone?.message} hint="10-digit Indian mobile">
              <input id="phone" inputMode="numeric" autoComplete="tel" className={inputCls} placeholder="9876543210" {...register("phone")} />
            </Field>
          </div>
          <Field label="Website" id="website" error={errors.website?.message} hint="Optional">
            <input id="website" className={inputCls} placeholder="https://company.com" {...register("website")} />
          </Field>

          <div className="rounded-lg border border-cardline bg-page p-3">
            <p className="text-xs text-muted">{notice ?? "Loading…"}</p>
            <label className="mt-2 flex items-start gap-2 text-sm text-ink">
              <input type="checkbox" className="mt-0.5 h-4 w-4 accent-[#1B5FE8]" {...register("consent_data_processing")} />
              <span>I consent to SPS Technosoft processing our company &amp; contact details for onboarding.</span>
            </label>
            {errors.consent_data_processing && <p className="mt-1 text-xs text-[#DC2626]">{errors.consent_data_processing.message}</p>}
          </div>

          <div>
            <HCaptcha sitekey={sitekey} onVerify={(t: string) => { setCaptchaToken(t); setCaptchaError(null); }} onExpire={() => setCaptchaToken(null)} />
            {captchaError && <p className="mt-1 text-xs text-[#DC2626]">{captchaError}</p>}
          </div>

          {formError && <p role="alert" className="rounded-lg bg-[#FEF2F2] px-3 py-2 text-sm text-[#DC2626]">{formError}</p>}

          <div className="flex items-center justify-between gap-3 pt-1">
            <Link href="/login?role=client" className="text-sm text-muted hover:text-ink">Already approved? Sign in</Link>
            <button type="submit" disabled={register_.isPending} className="rounded-lg bg-[#1B5FE8] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-60">
              {register_.isPending ? "Submitting…" : "Submit for review"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
