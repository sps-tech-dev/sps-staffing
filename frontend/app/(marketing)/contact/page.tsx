import type { Metadata } from "next";
import { ContactPage } from "../_design/site";

export const metadata: Metadata = { title: 'Contact — SPSTechnosoft', description: 'SPSTechnosoft connects businesses with top talent through staffing, education, and IT consulting.' };

export default function Page() {
  return <ContactPage />;
}
