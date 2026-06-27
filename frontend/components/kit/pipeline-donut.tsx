"use client";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
const COLORS = ["#1B5FE8","#5B8FFF","#E8A020","#0D1B3E","#6B7A9E","#16A34A"];
export function PipelineDonut({ segments }: { segments: { label: string; value: number }[] }) {
  return (
    <div className="h-56 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={segments} dataKey="value" nameKey="label" innerRadius="58%" outerRadius="85%" paddingAngle={2}>
            {segments.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
          </Pie>
          <Tooltip />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
