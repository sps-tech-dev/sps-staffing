import type { Metadata } from "next";
import { StaffingPage } from "../../_design/site";

export const metadata: Metadata = { title: 'Staffing & Recruitment — SPSTechnosoft', description: 'SPSTechnosoft connects businesses with top talent through staffing, education, and IT consulting.' };

export default function Page() {
  return <StaffingPage />;
}
