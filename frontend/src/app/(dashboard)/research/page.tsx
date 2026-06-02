"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { researchApi } from "@/lib/api";
import { formatRelativeTime, capitalize } from "@/lib/utils";
import { toast } from "sonner";
import { Search, Plus, Loader2, CheckCircle, AlertCircle, Clock, Trash2 } from "lucide-react";
import type { PaginatedResponse, ResearchSession } from "@/types";

const RESEARCH_TYPES = [
  { value: "web_search", label: "Web Search" },
  { value: "reddit_analysis", label: "Reddit Analysis" },
  { value: "multi_source", label: "Multi-Source" },
  { value: "competitive", label: "Competitive" },
];

export default function ResearchPage() {
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const [researchType, setResearchType] = useState("web_search");

  const { data, isLoading } = useQuery<PaginatedResponse<ResearchSession>>({
    queryKey: ["research-sessions"],
    queryFn: () => researchApi.list(),
    refetchInterval: 15_000,
  });

  const startMutation = useMutation({
    mutationFn: () => researchApi.start({ query, research_type: researchType }),
    onSuccess: () => {
      toast.success("Research session started");
      setQuery("");
      queryClient.invalidateQueries({ queryKey: ["research-sessions"] });
    },
    onError: () => toast.error("Failed to start research"),
  });

  const deleteMutation = useMutation({
    mutationFn: researchApi.delete,
    onSuccess: () => {
      toast.success("Session deleted");
      queryClient.invalidateQueries({ queryKey: ["research-sessions"] });
    },
  });

  const statusIcon = (status: string) => {
    if (status === "completed") return <CheckCircle size={14} className="text-green-500" />;
    if (status === "failed") return <AlertCircle size={14} className="text-red-500" />;
    if (status === "in_progress") return <Loader2 size={14} className="text-blue-500 animate-spin" />;
    return <Clock size={14} className="text-muted-foreground" />;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Search size={24} className="text-blue-500" />
        <div>
          <h1 className="text-2xl font-bold">Research Center</h1>
          <p className="text-muted-foreground text-sm">Multi-source intelligence research with AI synthesis</p>
        </div>
      </div>

      <div className="rounded-xl border border-border bg-card p-6">
        <h2 className="font-semibold mb-4">New Research Session</h2>
        <div className="space-y-3">
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="What do you want to research? Be specific. (e.g. 'What are the most common complaints about project management tools on Reddit in 2024?')"
            rows={3}
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring resize-none"
          />
          <div className="flex gap-3">
            <select
              value={researchType}
              onChange={(e) => setResearchType(e.target.value)}
              className="rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            >
              {RESEARCH_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
            <button
              onClick={() => query.length >= 3 && startMutation.mutate()}
              disabled={query.length < 3 || startMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
            >
              {startMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
              Start Research
            </button>
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-border bg-card divide-y divide-border">
        <div className="p-4 flex items-center justify-between">
          <h2 className="font-semibold">Research Sessions</h2>
          <span className="text-xs text-muted-foreground">{data?.total ?? 0} total</span>
        </div>
        {isLoading ? (
          <div className="p-8 text-center text-muted-foreground text-sm">Loading…</div>
        ) : !data?.items.length ? (
          <div className="p-8 text-center text-muted-foreground text-sm">
            No research sessions yet.
          </div>
        ) : (
          data.items.map((item) => (
            <div key={item.id} className="p-4 flex items-start justify-between hover:bg-accent/30 transition-colors">
              <div className="flex items-start gap-3 flex-1 min-w-0">
                <div className="mt-0.5">{statusIcon(item.status)}</div>
                <div className="min-w-0">
                  <p className="font-medium text-sm truncate">{item.title}</p>
                  <p className="text-xs text-muted-foreground mt-0.5 truncate">{item.query}</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {capitalize(item.research_type.replace("_", " "))} · {item.sources_count} sources
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-4 ml-4 shrink-0">
                {item.status === "completed" && (
                  <a href={`/research/${item.id}`} className="text-xs text-primary hover:underline">View</a>
                )}
                <span className="text-xs text-muted-foreground">{formatRelativeTime(item.created_at)}</span>
                <button onClick={() => deleteMutation.mutate(item.id)} className="text-muted-foreground hover:text-destructive transition-colors">
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
