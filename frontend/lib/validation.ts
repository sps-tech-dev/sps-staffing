import { z } from "zod";

/** Client-side field validation — mirrors the backend (app/validation.py).
 *  UX only; the backend re-validates and is authoritative. */

// Email: local part, '@', dotted domain (e.g. name@example.com).
export const emailSchema = z
  .string()
  .trim()
  .toLowerCase()
  .regex(/^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/, "Enter a valid email address (e.g. name@example.com)");

// Indian mobile: strip +91/0/spaces/dashes, then exactly 10 digits starting 6-9.
export const phoneSchema = z
  .string()
  .transform((s) => s.replace(/[\s\-()]/g, "").replace(/^(\+91|91|0)/, ""))
  .refine((v) => /^[6-9]\d{9}$/.test(v), "Enter a valid 10-digit Indian mobile number");

// Indian PAN: 5 letters, 4 digits, 1 letter (e.g. ABCDE1234F).
export const panSchema = z
  .string()
  .trim()
  .toUpperCase()
  .regex(/^[A-Z]{5}[0-9]{4}[A-Z]$/, "Enter a valid PAN (e.g. ABCDE1234F)");

// ── Common reusable field checks (compose these into every form schema) ──
export const requiredString = (label = "This field") =>
  z.string().trim().min(1, `${label} is required`);

// Person/company name: letters, spaces, . ' - & , 2–100 chars.
export const nameSchema = z
  .string()
  .trim()
  .min(2, "Must be at least 2 characters")
  .max(100, "Must be at most 100 characters")
  .regex(/^[A-Za-z][A-Za-z .,'&-]*$/, "Contains invalid characters");

// Strong password for registration / password-set (login uses a plain non-empty).
export const passwordSchema = z
  .string()
  .min(12, "Password must be at least 12 characters")
  .refine((v) => /[A-Za-z]/.test(v) && /\d/.test(v), "Include at least one letter and one number")
  .refine((v) => !/^(password|passw0rd|12345678|qwerty|letmein|welcome)/i.test(v), "Password is too weak");

// Years of experience: 0–60.
export const experienceSchema = z.coerce.number().int().min(0, "Cannot be negative").max(60, "Seems too high");

// 6-digit Indian PIN code.
export const pincodeSchema = z.string().trim().regex(/^\d{6}$/, "Enter a valid 6-digit PIN code");

// Optional URL (e.g. company website / LinkedIn).
export const urlSchema = z.string().trim().url("Enter a valid URL (https://…)");

export const loginSchema = z.object({
  email: emailSchema,
  password: requiredString("Password"),
});
export type LoginInput = z.infer<typeof loginSchema>;

// Candidate self-registration (multi-step). PAN/phone are encrypted server-side;
// data-processing consent is mandatory (DPDP — can't collect PAN without it).
export const registrationSchema = z.object({
  full_name: nameSchema,
  email: emailSchema,
  phone: phoneSchema,
  pan: panSchema,
  skills: z.string().trim().optional(), // comma-separated → split on submit
  total_exp: z
    .union([z.literal(""), experienceSchema])
    .optional()
    .transform((v) => (v === "" || v === undefined ? undefined : v)),
  consent_data_processing: z.literal(true, {
    errorMap: () => ({ message: "You must consent to data processing to register" }),
  }),
  consent_marketing: z.boolean().optional().default(false),
});
export type RegistrationInput = z.infer<typeof registrationSchema>;

// Fields validated per wizard step (used with RHF trigger() before advancing).
export const registrationSteps: (keyof RegistrationInput)[][] = [
  ["full_name", "email", "phone"],
  ["pan", "skills", "total_exp"],
  ["consent_data_processing", "consent_marketing"],
];

// Client (company) self-registration → a pending request (no access until approved).
export const clientRegistrationSchema = z.object({
  company_name: z.string().trim().min(2, "Company name is required"),
  industry: z.string().trim().optional(),
  contact_person: nameSchema,
  email: emailSchema,
  phone: phoneSchema,
  website: z.union([z.literal(""), urlSchema]).optional().transform((v) => (v ? v : undefined)),
  company_size: z.string().trim().optional(),
  consent_data_processing: z.literal(true, {
    errorMap: () => ({ message: "You must consent to data processing to register" }),
  }),
});
export type ClientRegistrationInput = z.infer<typeof clientRegistrationSchema>;
