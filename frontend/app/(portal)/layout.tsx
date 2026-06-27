/** In production, read the role from the verified session. The starter defaults
 *  to "candidate"; the employer route overrides via its own segment if needed.
 *  (Each page wraps itself in AppShell with the right role/title.) */
export default async function PortalLayout({ children }: { children: React.ReactNode }) {
  return children; // each page wraps itself in AppShell with the right role/title
}
