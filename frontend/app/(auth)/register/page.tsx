"use client";

import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import dynamic from "next/dynamic";
import Link from "next/link";
import { CheckCircle2, ShieldCheck } from "lucide-react";
import { registrationSchema, registrationSteps, type RegistrationInput } from "@/lib/validation";
import { useRegistrationConfig, useRegisterCandidate } from "@/lib/api/hooks";
import { ApiError } from "@/lib/api/client";

// hCaptcha is client-only (touches window) → load without SSR.
const HCaptcha = dynamic(() => import("@hcaptcha/react-hcaptcha"), { ssr: false });
// hCaptcha's official TEST sitekey — always passes. Real key is STOP-4 (account).
const TEST_SITEKEY = "10000000-ffff-ffff-ffff-000000000001";

const STEP_TITLES = ["Your profile", "Identity & skills", "Consent & verification"];

function Field({
  label, id, error, children, hint,
}: { label: string; id: string; error?: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-ink">{label}</label>
      {children}
      {hint && !error && <p className="mt-1 text-xs text-muted">{hint}</p>}
      {error && <p className="mt-1 text-xs text-[#DC2626]">{error}</p>}
    </div>
  );
}

const inputCls =
  "mt-1 w-full rounded-lg border border-cardline bg-white px-3 py-2 text-sm text-ink outline-none focus:border-[#1B5FE8]";

export default function RegisterPage() {
  const cfg = useRegistrationConfig();
  const register_ = useRegisterCandidate();
  const [step, setStep] = useState(0);
  const [captchaToken, setCaptchaToken] = useState<string | null>(null);
  const [captchaError, setCaptchaError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const {
    register, handleSubmit, trigger, setFocus, formState: { errors },
  } = useForm<RegistrationInput>({
    resolver: zodResolver(registrationSchema),
    mode: "onTouched",
    defaultValues: { consent_data_processing: false as unknown as true, consent_marketing: false },
  });

  // autofocus the first field of each step (keyboard convention)
  useEffect(() => { setFocus(registrationSteps[step][0]); }, [step, setFocus]);

  const isLast = step === registrationSteps.length - 1;

  async function onFormSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    if (!isLast) {
      if (await trigger(registrationSteps[step])) setStep((s) => s + 1);
      return;
    }
    handleSubmit(onValid)();
  }

  function onValid(data: RegistrationInput) {
    if (!captchaToken) { setCaptchaError("Please complete the captcha"); return; }
    const payload = {
      ...data,
      skills: data.skills ? data.skills.split(",").map((s) => s.trim()).filter(Boolean) : undefined,
      captcha_token: captchaToken,
    };
    register_.mutate(payload, {
      onSuccess: () => setDone(true),
      onError: (err) => {
        const e = err as ApiError;
        setFormError(
          e.code === "DUPLICATE_CANDIDATE"
            ? "You appear to be already registered (matching phone or PAN)."
            : e.code === "CONSENT_REQUIRED"
              ? "Consent to data processing is required."
              : e.code === "CAPTCHA_FAILED"
                ? "Captcha verification failed — please retry."
                : e.message || "Registration failed — please try again.",
        );
      },
    });
  }

  if (done) {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-page px-4">
        <div className="w-full max-w-md rounded-2xl border border-cardline bg-card p-8 text-center shadow-sm">
          <CheckCircle2 className="mx-auto mb-3 h-12 w-12 text-[#16A34A]" />
          <h1 className="text-xl font-semibold text-ink">You&apos;re registered</h1>
          <p className="mt-2 text-sm text-muted">
            Thanks for joining the talent pool. A recruiter will be in touch.
          </p>
          <Link href="/login?role=candidate" className="mt-6 inline-block rounded-lg bg-[#1B5FE8] px-5 py-2.5 text-sm font-semibold text-white">
            Go to login
          </Link>
        </div>
      </div>
    );
  }

  const notices = cfg.data?.notices;
  const sitekey = cfg.data?.hcaptcha_sitekey || TEST_SITEKEY;

  return (
    <div className="flex min-h-dvh items-center justify-center bg-page px-4 py-10">
      <div className="w-full max-w-lg rounded-2xl border border-cardline bg-card p-6 shadow-sm sm:p-8">
        <h1 className="text-xl font-semibold text-ink">Join the talent pool</h1>
        <p className="mt-1 text-sm text-muted">Step {step + 1} of {registrationSteps.length} — {STEP_TITLES[step]}</p>
        <div className="mt-3 flex gap-1.5" aria-hidden>
          {registrationSteps.map((_, i) => (
            <div key={i} className={`h-1.5 flex-1 rounded-full ${i <= step ? "bg-[#1B5FE8]" : "bg-cardline"}`} />
          ))}
        </div>

        <form onSubmit={onFormSubmit} className="mt-6 space-y-4" noValidate>
          {step === 0 && (
            <>
              <Field label="Full name" id="full_name" error={errors.full_name?.message}>
                <input id="full_name" className={inputCls} placeholder="Asha Sharma" {...register("full_name")} />
              </Field>
              <Field label="Email" id="email" error={errors.email?.message}>
                <input id="email" type="email" autoComplete="email" className={inputCls} placeholder="name@example.com" {...register("email")} />
              </Field>
              <Field label="Mobile" id="phone" error={errors.phone?.message} hint="10-digit Indian mobile">
                <input id="phone" inputMode="numeric" autoComplete="tel" className={inputCls} placeholder="9876543210" {...register("phone")} />
              </Field>
            </>
          )}

          {step === 1 && (
            <>
              <Field label="PAN" id="pan" error={errors.pan?.message} hint="Encrypted at rest — used only for verification">
                <input id="pan" className={`${inputCls} uppercase`} placeholder="ABCDE1234F" {...register("pan")} />
              </Field>
              <Field label="Skills" id="skills" error={errors.skills?.message} hint="Comma-separated (optional)">
                <input id="skills" className={inputCls} placeholder="python, sql, react" {...register("skills")} />
              </Field>
              <Field label="Years of experience" id="total_exp" error={errors.total_exp?.message} hint="Optional">
                <input id="total_exp" inputMode="numeric" className={inputCls} placeholder="4" {...register("total_exp")} />
              </Field>
            </>
          )}

          {step === 2 && (
            <>
              <div className="rounded-lg border border-cardline bg-page p-3">
                <div className="flex items-center gap-2 text-sm font-medium text-ink">
                  <ShieldCheck size={16} className="text-[#1B5FE8]" /> Data processing consent
                </div>
                <p className="mt-1 text-xs text-muted">{notices?.data_processing ?? "Loading…"}</p>
                <label className="mt-2 flex items-start gap-2 text-sm text-ink">
                  <input type="checkbox" className="mt-0.5 h-4 w-4 accent-[#1B5FE8]" {...register("consent_data_processing")} />
                  <span>I consent to SPS Technosoft processing my data (incl. PAN) for recruitment.</span>
                </label>
                {errors.consent_data_processing && (
                  <p className="mt-1 text-xs text-[#DC2626]">{errors.consent_data_processing.message}</p>
                )}
              </div>

              <label className="flex items-start gap-2 text-sm text-ink">
                <input type="checkbox" className="mt-0.5 h-4 w-4 accent-[#1B5FE8]" {...register("consent_marketing")} />
                <span>{notices?.marketing ?? "Send me occasional updates (optional)."}</span>
              </label>

              <div>
                <HCaptcha
                  sitekey={sitekey}
                  onVerify={(t: string) => { setCaptchaToken(t); setCaptchaError(null); }}
                  onExpire={() => setCaptchaToken(null)}
                />
                {captchaError && <p className="mt-1 text-xs text-[#DC2626]">{captchaError}</p>}
              </div>
            </>
          )}

          {formError && <p role="alert" className="rounded-lg bg-[#FEF2F2] px-3 py-2 text-sm text-[#DC2626]">{formError}</p>}

          <div className="flex items-center justify-between gap-3 pt-1">
            {step > 0 ? (
              <button type="button" onClick={() => setStep((s) => s - 1)} className="rounded-lg border border-cardline px-4 py-2 text-sm text-muted">
                Back
              </button>
            ) : (
              <Link href="/login?role=candidate" className="text-sm text-muted hover:text-ink">Have an account? Sign in</Link>
            )}
            <button
              type="submit"
              disabled={register_.isPending}
              className="rounded-lg bg-[#1B5FE8] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-60"
            >
              {isLast ? (register_.isPending ? "Submitting…" : "Register") : "Continue"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
