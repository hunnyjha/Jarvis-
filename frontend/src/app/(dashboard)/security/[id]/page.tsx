"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { securityApi } from "@/lib/api";
import { capitalize, formatRelativeTime, severityColor } from "@/lib/utils";
import { ArrowLeft, Shield, AlertCircle, Loader2 } from "lucide-react";

export default function SecurityDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const { data: inv, isLoading } = useQuery({
    queryKey: ["security-investigation", id],
    queryFn: () => securityApi.get(id),
    refetchInterval: (query) => {
      const data = query.state.data as any;
      return data?.status === "in_progress" ? 3000 : false;
    },
  });

  const riskBg: Record<string, string> = {
    critical: "bg-red-500/10 border-red-500/20 text-red-500",
    high: "bg-orange-500/10 border-orange-500/20 text-orange-500",
    medium: "bg-yellow-500/10 border-yellow-500/20 text-yellow-500",
    low: "bg-blue-500/10 border-blue-500/20 text-blue-500",
    info: "bg-gray-500/10 border-gray-500/20 text-gray-500",
  };

  if (isLoading) return <div className="flex h-64 items-center justify-center"><Loader2 className="animate-spin" /></div>;
  if (!inv) return <div className="text-center text-muted-foreground p-8">Investigation not found</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <button onClick={() => router.back()} className="p-2 hover:bg-accent rounded-lg transition-colors">
          <ArrowLeft size={16} />
        </button>
        <div>
          <h1 className="text-2xl font-bold">{inv.title}</h1>
          <p className="text-sm text-muted-foreground">
            Target: {inv.target} · {inv.findings_count} findings · {formatRelativeTime(inv.created_at)}
          </p>
        </div>
      </div>

      {inv.status === "in_progress" && (
        <div className="flex items-center gap-3 p-4 rounded-xl border border-blue-500/20 bg-blue-500/5 text-blue-400 text-sm">
          <Loader2 size={14} className="animate-spin" /> Investigation in progress…
        </div>
      )}

      {inv.status === "completed" && (
        <>
          {inv.risk_level && (
            <div className={`p-4 rounded-xl border ${riskBg[inv.risk_level] || riskBg.info}`}>
              <p className="font-semibold text-sm">
                Risk Level: {capitalize(inv.risk_level)}
                {inv.risk_score != null && <span className="ml-2 opacity-70">({inv.risk_score.toFixed(0)}/100)</span>}
              </p>
            </div>
          )}

          {inv.executive_summary && (
            <div className="rounded-xl border border-border bg-card p-6">
              <h2 className="font-semibold mb-3 flex items-center gap-2">
                <Shield size={16} className="text-red-500" /> Executive Summary
              </h2>
              <p className="text-sm leading-relaxed text-muted-foreground">{inv.executive_summary}</p>
            </div>
          )}

          {inv.findings && inv.findings.length > 0 && (
            <div className="rounded-xl border border-border bg-card">
              <div className="p-4 border-b border-border">
                <h2 className="font-semibold">Findings ({inv.findings.length})</h2>
              </div>
              <div className="divide-y divide-border">
                {inv.findings.map((f: any) => (
                  <div key={f.id} className="p-4">
                    <div className="flex items-start gap-3">
                      <span className={`text-xs font-medium px-2 py-1 rounded-full border ${riskBg[f.severity] || riskBg.info} shrink-0`}>
                        {capitalize(f.severity)}
                      </span>
                      <div className="flex-1">
                        <p className="font-medium text-sm">{f.title}</p>
                        {f.description && (
                          <p className="text-xs text-muted-foreground mt-1">{f.description}</p>
                        )}
                        {f.confidence_score != null && (
                          <p className="text-xs text-muted-foreground mt-1">
                            Confidence: {(f.confidence_score * 100).toFixed(0)}%
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {inv.recommendations && (
            <div className="rounded-xl border border-border bg-card p-6">
              <h2 className="font-semibold mb-4">Recommendations</h2>
              {Object.entries(inv.recommendations).map(([category, items]) => (
                <div key={category} className="mb-4">
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                    {category.replace(/_/g, " ")}
                  </p>
                  {Array.isArray(items) ? (
                    <ul className="space-y-1">
                      {(items as string[]).map((item, i) => (
                        <li key={i} className="text-sm text-muted-foreground flex items-start gap-2">
                          <span className="text-primary">→</span> {item}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-sm text-muted-foreground">{String(items)}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
