"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { researchApi } from "@/lib/api";
import { capitalize, formatRelativeTime } from "@/lib/utils";
import { ArrowLeft, Search, ExternalLink, Loader2, AlertCircle } from "lucide-react";

export default function ResearchDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const { data: session, isLoading } = useQuery({
    queryKey: ["research-session", id],
    queryFn: () => researchApi.get(id),
    refetchInterval: (query) => {
      const data = query.state.data as any;
      return data?.status === "in_progress" ? 3000 : false;
    },
  });

  if (isLoading) return <div className="flex h-64 items-center justify-center"><Loader2 className="animate-spin" /></div>;
  if (!session) return <div className="text-center text-muted-foreground p-8">Session not found</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <button onClick={() => router.back()} className="p-2 hover:bg-accent rounded-lg transition-colors">
          <ArrowLeft size={16} />
        </button>
        <div>
          <h1 className="text-2xl font-bold">{session.title}</h1>
          <p className="text-sm text-muted-foreground">
            {capitalize(session.research_type.replace("_", " "))} · {session.sources_count} sources ·{" "}
            {formatRelativeTime(session.created_at)}
          </p>
        </div>
      </div>

      {session.status === "in_progress" && (
        <div className="flex items-center gap-3 p-4 rounded-xl border border-blue-500/20 bg-blue-500/5 text-blue-400 text-sm">
          <Loader2 size={14} className="animate-spin" /> Research in progress…
        </div>
      )}

      {session.status === "failed" && (
        <div className="p-4 rounded-xl border border-destructive/20 bg-destructive/5 text-destructive text-sm">
          <AlertCircle size={14} className="inline mr-2" />{session.error_message || "Research failed"}
        </div>
      )}

      {session.status === "completed" && (
        <>
          <div className="rounded-xl border border-border bg-card p-6">
            <h2 className="font-semibold mb-3 flex items-center gap-2">
              <Search size={16} className="text-blue-500" /> Research Query
            </h2>
            <p className="text-sm text-muted-foreground">{session.query}</p>
          </div>

          {session.summary && (
            <div className="rounded-xl border border-border bg-card p-6">
              <h2 className="font-semibold mb-3">Summary</h2>
              <p className="text-sm leading-relaxed text-muted-foreground">{session.summary}</p>
            </div>
          )}

          {session.metadata?.key_findings && (
            <div className="rounded-xl border border-border bg-card p-6">
              <h2 className="font-semibold mb-4">Key Findings</h2>
              <ul className="space-y-2">
                {(session.metadata.key_findings as string[]).map((f: string, i: number) => (
                  <li key={i} className="flex items-start gap-2 text-sm">
                    <span className="text-primary font-bold mt-0.5">{i + 1}.</span>
                    <span className="text-muted-foreground">{f}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {session.results && session.results.length > 0 && (
            <div className="rounded-xl border border-border bg-card">
              <div className="p-4 border-b border-border">
                <h2 className="font-semibold">Sources ({session.results.length})</h2>
              </div>
              <div className="divide-y divide-border">
                {session.results.map((result: any) => (
                  <div key={result.id} className="p-4 hover:bg-accent/20 transition-colors">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-sm">{result.title}</p>
                        {result.snippet && (
                          <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{result.snippet}</p>
                        )}
                        <p className="text-xs text-muted-foreground mt-1">{result.source}</p>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        {result.relevance_score != null && (
                          <span className="text-xs text-muted-foreground">
                            {(result.relevance_score * 100).toFixed(0)}% relevant
                          </span>
                        )}
                        {result.url && (
                          <a href={result.url} target="_blank" rel="noopener noreferrer"
                            className="text-primary hover:text-primary/80 transition-colors">
                            <ExternalLink size={14} />
                          </a>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
