"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { securityApi } from "@/lib/api";
import { formatRelativeTime, capitalize, severityColor } from "@/lib/utils";
import { toast } from "sonner";
import { Shield, Plus, Loader2, AlertCircle, CheckCircle, Clock, Trash2 } from "lucide-react";
import type { PaginatedResponse, SecurityInvestigation } from "@/types";

const INVESTIGATION_TYPES = [
  { value: "account_scan", label: "Account Scan" },
  { value: "threat_assessment", label: "Threat Assessment" },
  { value: "osint_collection", label: "OSINT Collection" },
];

export default function SecurityPage() {
  const queryClient = useQueryClient();
  const [target, setTarget] = useState("");
  const [invType, setInvType] = useState("account_scan");

  const { data, isLoading } = useQuery<PaginatedResponse<SecurityInvestigation>>({
    queryKey: ["security-investigations"],
    queryFn: () => securityApi.list(),
    refetchInterval: 15_000,
  });

  const investigateMutation = useMutation({
    mutationFn: () => securityApi.investigate({ target, investigation_type: invType }),
    onSuccess: () => {
      toast.success(`Investigation started for ${target}`);
      setTarget("");
      queryClient.invalidateQueries({ queryKey: ["security-investigations"] });
    },
    onError: () => toast.error("Failed to start investigation"),
  });

  const deleteMutation = useMutation({
    mutationFn: securityApi.delete,
    onSuccess: () => {
      toast.success("Investigation deleted");
      queryClient.invalidateQueries({ queryKey: ["security-investigations"] });
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
        <Shield size={24} className="text-red-500" />
        <div>
          <h1 className="text-2xl font-bold">Security Center</h1>
          <p className="text-muted-foreground text-sm">Investigate Reddit accounts, detect manipulation, analyze threats</p>
        </div>
      </div>

      <div className="rounded-xl border border-destructive/20 bg-destructive/5 p-4 text-sm text-muted-foreground">
        <strong className="text-foreground">Research use only.</strong> Only investigate public information on accounts you have authorization to analyze.
      </div>

      <div className="rounded-xl border border-border bg-card p-6">
        <h2 className="font-semibold mb-4">New Investigation</h2>
        <div className="flex gap-3">
          <input
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            placeholder="Reddit username (e.g. spez)"
            className="flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            onKeyDown={(e) => e.key === "Enter" && target && investigateMutation.mutate()}
          />
          <select
            value={invType}
            onChange={(e) => setInvType(e.target.value)}
            className="rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          >
            {INVESTIGATION_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
          <button
            onClick={() => target && investigateMutation.mutate()}
            disabled={!target || investigateMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 rounded-md bg-destructive text-destructive-foreground text-sm font-medium hover:bg-destructive/90 disabled:opacity-50 transition-colors"
          >
            {investigateMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
            Investigate
          </button>
        </div>
      </div>

      <div className="rounded-xl border border-border bg-card divide-y divide-border">
        <div className="p-4 flex items-center justify-between">
          <h2 className="font-semibold">Investigations</h2>
          <span className="text-xs text-muted-foreground">{data?.total ?? 0} total</span>
        </div>
        {isLoading ? (
          <div className="p-8 text-center text-muted-foreground text-sm">Loading…</div>
        ) : !data?.items.length ? (
          <div className="p-8 text-center text-muted-foreground text-sm">No investigations yet.</div>
        ) : (
          data.items.map((item) => (
            <div key={item.id} className="p-4 flex items-center justify-between hover:bg-accent/30 transition-colors">
              <div className="flex items-center gap-3">
                {statusIcon(item.status)}
                <div>
                  <p className="font-medium text-sm">{item.title}</p>
                  <p className="text-xs text-muted-foreground">
                    {capitalize(item.investigation_type.replace("_", " "))} · {item.findings_count} findings
                    {item.risk_level && (
                      <span className={`ml-2 ${severityColor(item.risk_level)}`}>
                        {capitalize(item.risk_level)} risk
                      </span>
                    )}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                {item.status === "completed" && (
                  <a href={`/security/${item.id}`} className="text-xs text-primary hover:underline">View</a>
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
