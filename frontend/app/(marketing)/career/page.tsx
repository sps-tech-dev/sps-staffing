import type { Metadata } from "next";
import { CareerPage } from "../_design/site";

export const metadata: Metadata = { title: 'Careers — SPSTechnosoft', description: 'SPSTechnosoft connects businesses with top talent through staffing, education, and IT consulting.' };

export default function Page() {
  return <CareerPage />;
}
