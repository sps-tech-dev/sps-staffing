import type { Metadata } from "next";
import { ServicesPage } from "../_design/site";

export const metadata: Metadata = { title: 'Services — SPSTechnosoft', description: 'SPSTechnosoft connects businesses with top talent through staffing, education, and IT consulting.' };

export default function Page() {
  return <ServicesPage />;
}
