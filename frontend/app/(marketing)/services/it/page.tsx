import type { Metadata } from "next";
import { ITServicesPage } from "../../_design/site";

export const metadata: Metadata = { title: 'IT Services & Consulting — SPSTechnosoft', description: 'SPSTechnosoft connects businesses with top talent through staffing, education, and IT consulting.' };

export default function Page() {
  return <ITServicesPage />;
}
