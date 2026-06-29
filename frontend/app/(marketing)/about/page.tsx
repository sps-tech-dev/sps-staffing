import type { Metadata } from "next";
import { AboutPage } from "../_design/site";

export const metadata: Metadata = { title: 'About — SPSTechnosoft', description: 'SPSTechnosoft connects businesses with top talent through staffing, education, and IT consulting.' };

export default function Page() {
  return <AboutPage />;
}
