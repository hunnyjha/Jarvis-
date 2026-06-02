"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { redditApi, reportsApi } from "@/lib/api";
import { formatNumber, formatRelativeTime, capitalize } from "@/lib/utils";
import { toast } from "sonner";
import {
  ArrowLeft, Bot, Users, TrendingUp, MessageSquare,
  FileText, AlertCircle, CheckCircle, Loader2,
} from "lucide-react";

export default function RedditAnalysisDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const { data: analysis, isLoading } = useQuery({
    queryKey: ["reddit-analysis", id],
    queryFn: () => redditApi.get(id),
    refetchInterval: (query) => {
      const data = query.state.data as any;
      return data?.status === "in_progress" ? 3000 : false;
    },
  });

  const handleGenerateReport = async () => {
    try {
      await reportsApi.generate({
        title: `r/${analysis?.subreddit_name} Analysis Report`,
        report_type: "subreddit_analysis",
        source_id: id,
        format: "markdown",
      });
      toast.success("Report generation started");
      router.push("/reports");
    } catch {
      toast.error("Failed to generate report");
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="animate-spin text-muted-foreground" />
      </div>
    );
  }
  if (!analysis) {
    return <div className="text-center text-muted-foreground p-8">Analysis not found</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.back()}
            className="p-2 hover:bg-accent rounded-lg transition-colors"
          >
            <ArrowLeft size={16} />
          </button>
          <div>
            <h1 className="text-2xl font-bold">r/{analysis.subreddit_name}</h1>
            <p className="text-muted-foreground text-sm">
              {capitalize(analysis.status)} · {capitalize(analysis.time_period)} ·{" "}
              {analysis.posts_analyzed} posts
            </p>
          </div>
        </div>
        {analysis.status === "completed" && (
          <button
            onClick={handleGenerateReport}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            <FileText size={14} />
            Generate Report
          </button>
        )}
      </div>

      {analysis.status === "in_progress" && (
        <div className="flex items-center gap-3 p-4 rounded-xl border border-blue-500/20 bg-blue-500/5 text-blue-400 text-sm">
          <Loader2 size={14} className="animate-spin" />
          Analysis in progress — refreshing automatically…
        </div>
      )}

      {analysis.status === "failed" && (
        <div className="p-4 rounded-xl border border-destructive/20 bg-destructive/5 text-destructive text-sm">
          <AlertCircle size={14} className="inline mr-2" />
          {analysis.error_message || "Analysis failed"}
        </div>
      )}

      {analysis.status === "completed" && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: "Subscribers", value: formatNumber(analysis.subscriber_count || 0) },
              { label: "Active Users", value: formatNumber(analysis.active_users || 0) },
              { label: "Avg Score", value: Math.round(analysis.avg_score || 0).toLocaleString() },
              { label: "Avg Comments", value: Math.round(analysis.avg_comments || 0).toLocaleString() },
            ].map(({ label, value }) => (
              <div key={label} className="rounded-xl border border-border bg-card p-4">
                <p className="text-xs text-muted-foreground mb-1">{label}</p>
                <p className="text-xl font-bold">{value}</p>
              </div>
            ))}
          </div>

          {analysis.ai_summary && (
            <div className="rounded-xl border border-border bg-card p-6">
              <h2 className="font-semibold mb-3 flex items-center gap-2">
                <Bot size={16} className="text-orange-500" /> AI Summary
              </h2>
              <p className="text-sm text-muted-foreground leading-relaxed">{analysis.ai_summary}</p>
            </div>
          )}

          <div className="grid md:grid-cols-2 gap-4">
            {analysis.key_insights && (
              <div className="rounded-xl border border-border bg-card p-6">
                <h2 className="font-semibold mb-4">Key Insights</h2>
                <div className="space-y-3">
                  {Object.entries(analysis.key_insights).map(([k, v]) => (
                    <div key={k}>
                      <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">
                        {k.replace(/_/g, " ")}
                      </p>
                      <p className="text-sm">{String(v)}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {analysis.opportunities && (
              <div className="rounded-xl border border-border bg-card p-6">
                <h2 className="font-semibold mb-4">Opportunities</h2>
                {(analysis.opportunities as any).content_gaps?.map((g: string, i: number) => (
                  <div key={i} className="flex items-start gap-2 mb-2">
                    <CheckCircle size={12} className="text-green-500 mt-1 shrink-0" />
                    <p className="text-sm">{g}</p>
                  </div>
                ))}
                {(analysis.opportunities as any).growth_opportunities?.map((o: string, i: number) => (
                  <div key={i} className="flex items-start gap-2 mb-2">
                    <TrendingUp size={12} className="text-blue-500 mt-1 shrink-0" />
                    <p className="text-sm">{o}</p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {analysis.top_topics && (
            <div className="rounded-xl border border-border bg-card p-6">
              <h2 className="font-semibold mb-4">Top Topics</h2>
              <div className="flex flex-wrap gap-2">
                {Object.entries(analysis.top_topics)
                  .sort(([, a], [, b]) => (b as number) - (a as number))
                  .slice(0, 20)
                  .map(([topic, count]) => (
                    <span key={topic} className="px-3 py-1.5 rounded-full bg-primary/10 text-primary text-xs font-medium">
                      {topic} <span className="opacity-60">{String(count)}</span>
                    </span>
                  ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
