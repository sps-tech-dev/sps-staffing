import Link from "next/link";
export default function NotFound() {
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-4 bg-page">
      <h1 className="font-display text-3xl font-extrabold text-ink">404</h1>
      <p className="text-muted">This page could not be found.</p>
      <Link href="/" className="rounded-full bg-sps-blue px-5 py-2.5 text-sm font-semibold text-white">Go home</Link>
    </div>
  );
}
