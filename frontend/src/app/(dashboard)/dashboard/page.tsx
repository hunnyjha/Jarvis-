"use client";

import { useQuery } from "@tanstack/react-query";
import { dashboardApi } from "@/lib/api";
import type { DashboardStats } from "@/types";
import {
  BarChart3,
  Brain,
  FileText,
  Search,
  Shield,
  TrendingUp,
} from "lucide-react";
import Link from "next/link";

function StatCard({
  title,
  value,
  icon: Icon,
  href,
  color,
}: {
  title: string;
  value: number;
  icon: React.ElementType;
  href: string;
  color: string;
}) {
  return (
    <Link
      href={href}
      className="block rounded-xl border border-border bg-card p-5 hover:border-primary/50 transition-colors"
    >
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium text-muted-foreground">{title}</span>
        <div className={`p-2 rounded-lg ${color}`}>
          <Icon className="h-4 w-4" />
        </div>
      </div>
      <p className="text-3xl font-bold text-foreground">{value.toLocaleString()}</p>
    </Link>
  );
}

export default function DashboardPage() {
  const { data: stats, isLoading: statsLoading } = useQuery<DashboardStats>({
    queryKey: ["dashboard", "stats"],
    queryFn: dashboardApi.stats,
    refetchInterval: 30000,
  });

  const { data: activity, isLoading: activityLoading } = useQuery({
    queryKey: ["dashboard", "activity"],
    queryFn: dashboardApi.activity,
    refetchInterval: 60000,
  });

  const { data: recentReports } = useQuery({
    queryKey: ["dashboard", "recent-reports"],
    queryFn: dashboardApi.recentReports,
  });

  if (statsLoading) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="h-8 bg-muted rounded w-48" />
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-28 bg-muted rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-foreground">Dashboard</h1>
        <p className="text-muted-foreground text-sm mt-1">
          JARVIS AI Operating System — Overview
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard
          title="Research Sessions"
          value={stats?.research_sessions ?? 0}
          icon={Search}
          href="/research"
          color="bg-blue-500/10 text-blue-500"
        />
        <StatCard
          title="Reddit Analyses"
          value={stats?.subreddit_analyses ?? 0}
          icon={BarChart3}
          href="/reddit"
          color="bg-orange-500/10 text-orange-500"
        />
        <StatCard
          title="Investigations"
          value={stats?.security_investigations ?? 0}
          icon={Shield}
          href="/security"
          color="bg-red-500/10 text-red-500"
        />
        <StatCard
          title="Memories"
          value={stats?.memories ?? 0}
          icon={Brain}
          href="/memory"
          color="bg-purple-500/10 text-purple-500"
        />
        <StatCard
          title="Reports"
          value={stats?.reports ?? 0}
          icon={FileText}
          href="/reports"
          color="bg-green-500/10 text-green-500"
        />
      </div>

      {/* Quick Actions */}
      <div>
        <h2 className="text-base font-semibold mb-3 text-foreground">Quick Actions</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { label: "Analyze Subreddit", href: "/reddit", icon: BarChart3, color: "bg-orange-500" },
            { label: "Start Research", href: "/research", icon: Search, color: "bg-blue-500" },
            { label: "Investigate Target", href: "/security", icon: Shield, color: "bg-red-500" },
            { label: "View Reports", href: "/reports", icon: FileText, color: "bg-green-500" },
          ].map((action) => (
            <Link
              key={action.href}
              href={action.href}
              className="flex items-center gap-3 rounded-lg border border-border bg-card p-3 hover:border-primary/50 transition-colors"
            >
              <div className={`p-2 rounded-md ${action.color}/10`}>
                <action.icon className={`h-4 w-4 ${action.color.replace("bg-", "text-")}`} />
              </div>
              <span className="text-sm font-medium">{action.label}</span>
            </Link>
          ))}
        </div>
      </div>

      {/* Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="rounded-xl border border-border bg-card p-5">
          <h2 className="text-base font-semibold mb-4 flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-primary" />
            Recent Activity
          </h2>
          {activityLoading ? (
            <div className="space-y-3 animate-pulse">
              {[...Array(4)].map((_, i) => <div key={i} className="h-10 bg-muted rounded" />)}
            </div>
          ) : activity?.length ? (
            <ul className="space-y-2">
              {(activity as Array<{ type: string; id: string; title: string; status: string; created_at: string }>).map((item) => (
                <li
                  key={item.id}
                  className="flex items-center justify-between text-sm py-2 border-b border-border last:border-0"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-xs px-1.5 py-0.5 rounded bg-muted text-muted-foreground capitalize shrink-0">
                      {item.type.replace("_", " ")}
                    </span>
                    <span className="truncate">{item.title}</span>
                  </div>
                  <span className={`text-xs shrink-0 ml-2 ${
                    item.status === "completed" ? "text-green-500" :
                    item.status === "failed" ? "text-red-500" :
                    item.status === "in_progress" ? "text-yellow-500" :
                    "text-muted-foreground"
                  }`}>
                    {item.status}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-muted-foreground text-sm text-center py-6">
              No recent activity. Start by analyzing a subreddit!
            </p>
          )}
        </div>

        <div className="rounded-xl border border-border bg-card p-5">
          <h2 className="text-base font-semibold mb-4 flex items-center gap-2">
            <FileText className="h-4 w-4 text-primary" />
            Recent Reports
          </h2>
          {recentReports?.length ? (
            <ul className="space-y-2">
              {(recentReports as Array<{ id: string; title: string; report_type: string; status: string; created_at: string }>).map((report) => (
                <li key={report.id} className="flex items-center justify-between text-sm py-2 border-b border-border last:border-0">
                  <div className="min-w-0">
                    <p className="truncate font-medium">{report.title}</p>
                    <p className="text-xs text-muted-foreground capitalize">{report.report_type.replace(/_/g, " ")}</p>
                  </div>
                  <span className={`text-xs shrink-0 ml-2 ${report.status === "completed" ? "text-green-500" : report.status === "failed" ? "text-red-500" : "text-yellow-500"}`}>
                    {report.status}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-muted-foreground text-sm text-center py-6">
              No reports yet. Generate your first report!
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
