"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { redditApi } from "@/lib/api";
import type { SubredditAnalysis, PaginatedResponse } from "@/types";
import { formatRelativeTime } from "@/lib/utils";
import { BarChart3, Loader2, Plus, Trash2, ChevronRight, Clock, CheckCircle2, XCircle, AlertCircle } from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";

function StatusIcon({ status }: { status: string }) {
  if (status === "completed") return <CheckCircle2 className="h-4 w-4 text-emerald-500" />;
  if (status === "failed") return <XCircle className="h-4 w-4 text-red-500" />;
  if (status === "in_progress") return <Loader2 className="h-4 w-4 text-amber-500 animate-spin" />;
  return <Clock className="h-4 w-4 text-muted-foreground" />;
}

export default function RedditPage() {
  const [subreddit, setSubreddit] = useState("");
  const [timePeriod, setTimePeriod] = useState("week");
  const [postLimit, setPostLimit] = useState(100);
  const qc = useQueryClient();

  const { data, isLoading } = useQuery<PaginatedResponse<SubredditAnalysis>>({
    queryKey: ["reddit", "analyses"],
    queryFn: () => redditApi.list(1),
    refetchInterval: 10000,
  });

  const analyzeMutation = useMutation({
    mutationFn: () => redditApi.analyze({ subreddit_name: subreddit.replace(/^r\//, ""), time_period: timePeriod, post_limit: postLimit }),
    onSuccess: () => {
      toast.success(`Analysis started for r/${subreddit.replace(/^r\//, "")}`);
      setSubreddit("");
      qc.invalidateQueries({ queryKey: ["reddit"] });
    },
    onError: () => toast.error("Failed to start analysis"),
  });

  const deleteMutation = useMutation({
    mutationFn: redditApi.delete,
    onSuccess: () => { toast.success("Analysis deleted"); qc.invalidateQueries({ queryKey: ["reddit"] }); },
    onError: () => toast.error("Failed to delete"),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!subreddit.trim()) return;
    analyzeMutation.mutate();
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <BarChart3 className="h-6 w-6 text-orange-500" />
          Reddit Intelligence
        </h1>
        <p className="text-muted-foreground text-sm mt-1">
          Analyze subreddits for trends, sentiment, engagement, and opportunities
        </p>
      </div>

      {/* Analyze Form */}
      <div className="rounded-xl border border-border bg-card p-6">
        <h2 className="font-semibold mb-4">Analyze a Subreddit</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="flex gap-3 flex-wrap">
            <div className="flex-1 min-w-[200px]">
              <label className="block text-sm font-medium mb-1.5 text-muted-foreground">Subreddit</label>
              <input
                value={subreddit}
                onChange={(e) => setSubreddit(e.target.value)}
                placeholder="e.g. MachineLearning or r/python"
                className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1.5 text-muted-foreground">Time Period</label>
              <select
                value={timePeriod}
                onChange={(e) => setTimePeriod(e.target.value)}
                className="h-10 rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {["hour", "day", "week", "month", "year", "all"].map((t) => (
                  <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1.5 text-muted-foreground">Post Limit</label>
              <select
                value={postLimit}
                onChange={(e) => setPostLimit(Number(e.target.value))}
                className="h-10 rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {[25, 50, 100, 200, 500].map((n) => (
                  <option key={n} value={n}>{n} posts</option>
                ))}
              </select>
            </div>
          </div>
          <button
            type="submit"
            disabled={analyzeMutation.isPending || !subreddit.trim()}
            className="inline-flex items-center gap-2 h-10 px-5 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {analyzeMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            Start Analysis
          </button>
        </form>
      </div>

      {/* Analysis History */}
      <div>
        <h2 className="font-semibold mb-3 text-foreground">Analysis History</h2>
        {isLoading ? (
          <div className="space-y-3">
            {[...Array(3)].map((_, i) => <div key={i} className="h-16 bg-muted animate-pulse rounded-xl" />)}
          </div>
        ) : data?.items?.length ? (
          <div className="space-y-2">
            {data.items.map((analysis) => (
              <div key={analysis.id} className="flex items-center gap-4 rounded-xl border border-border bg-card px-4 py-3 hover:border-primary/40 transition-colors">
                <StatusIcon status={analysis.status} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm">r/{analysis.subreddit_name}</span>
                    <span className="text-xs text-muted-foreground">· {analysis.time_period}</span>
                    {analysis.status === "completed" && (
                      <span className="text-xs text-muted-foreground">· {analysis.posts_analyzed} posts</span>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {formatRelativeTime(analysis.created_at)}
                    {analysis.overall_sentiment && ` · ${analysis.overall_sentiment.replace("_", " ")}`}
                  </p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {analysis.status === "completed" && (
                    <Link
                      href={`/reddit/${analysis.id}`}
                      className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                    >
                      View <ChevronRight className="h-3 w-3" />
                    </Link>
                  )}
                  <button
                    onClick={() => deleteMutation.mutate(analysis.id)}
                    disabled={deleteMutation.isPending}
                    className="p-1.5 text-muted-foreground hover:text-destructive transition-colors rounded"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-12 text-muted-foreground rounded-xl border border-dashed border-border">
            <BarChart3 className="h-8 w-8 mx-auto mb-3 opacity-30" />
            <p className="text-sm">No analyses yet. Enter a subreddit above to get started.</p>
          </div>
        )}
      </div>
    </div>
  );
}
