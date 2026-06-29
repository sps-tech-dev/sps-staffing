import type { Metadata } from "next";
import { HomePage } from "./_design/site";

export const metadata: Metadata = { title: 'SPSTechnosoft — Staffing, Education & IT Consulting', description: 'SPSTechnosoft connects businesses with top talent through staffing, education, and IT consulting.' };

export default function Page() {
  return <HomePage />;
}
