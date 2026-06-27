"use client";
import { Sparkles } from "lucide-react";
import { SectionCard } from "@/components/kit/section-card";
import { Skeleton } from "@/components/kit/skeleton";
import { useAiCandidateSummary, useFeatures } from "@/lib/api/hooks";

// F6: AI widget gated behind the `ai` feature flag. Renders NOTHING when the flag
// is off (the server also 404s the endpoint), so the surface is fully gated.
export function AiInsightsCard({ candidateId }: { candidateId: string | null }) {
  const { data: feat } = useFeatures();
  const aiOn = !!feat?.features.ai;
  const summary = useAiCandidateSummary(candidateId, aiOn);

  if (!aiOn) return null;

  return (
    <div className="mt-4">
      <SectionCard title="AI insights (beta)">
        {!candidateId ? (
          <p className="text-sm text-muted">Select a job with candidates to see an AI summary.</p>
        ) : summary.isLoading ? (
          <Skeleton className="h-16" />
        ) : summary.isError || !summary.data ? (
          <p className="text-sm text-muted">Couldn&apos;t generate insights right now.</p>
        ) : (
          <div className="space-y-2">
            <div className="flex items-start gap-2 text-sm font-medium text-ink">
              <Sparkles size={16} className="mt-0.5 shrink-0 text-[#1B5FE8]" />
              <span>{summary.data.summary}</span>
            </div>
            {summary.data.highlights.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {summary.data.highlights.map((h) => (
                  <span key={h} className="rounded-full bg-page px-2 py-0.5 text-xs text-muted">{h}</span>
                ))}
              </div>
            )}
            <p className="text-xs text-muted">{summary.data.disclaimer}</p>
          </div>
        )}
      </SectionCard>
    </div>
  );
}
