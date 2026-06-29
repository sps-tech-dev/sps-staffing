import type { Metadata } from "next";
import { EducationPage } from "../../_design/site";

export const metadata: Metadata = { title: 'Education & Training — SPSTechnosoft', description: 'SPSTechnosoft connects businesses with top talent through staffing, education, and IT consulting.' };

export default function Page() {
  return <EducationPage />;
}
