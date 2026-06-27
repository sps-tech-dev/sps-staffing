export function SectionCard({ title, actions, children }:
  { title: string; actions?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="rounded-[14px] border border-cardline bg-card p-5 shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
      <header className="mb-4 flex items-center justify-between">
        <h3 className="font-display text-base font-bold text-ink">{title}</h3>
        {actions}
      </header>
      {children}
    </section>
  );
}
