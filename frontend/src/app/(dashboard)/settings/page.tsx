"use client";

import { useTheme } from "next-themes";
import { useAuthStore } from "@/store/authStore";
import { Settings, Sun, Moon, Monitor } from "lucide-react";

export default function SettingsPage() {
  const { theme, setTheme } = useTheme();
  const { user } = useAuthStore();

  const THEMES = [
    { value: "light", label: "Light", icon: Sun },
    { value: "dark", label: "Dark", icon: Moon },
    { value: "system", label: "System", icon: Monitor },
  ];

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center gap-3">
        <Settings size={24} className="text-muted-foreground" />
        <div>
          <h1 className="text-2xl font-bold">Settings</h1>
          <p className="text-muted-foreground text-sm">Configure JARVIS preferences</p>
        </div>
      </div>

      {/* Theme */}
      <div className="rounded-xl border border-border bg-card p-6">
        <h2 className="font-semibold mb-4">Appearance</h2>
        <div className="flex gap-3">
          {THEMES.map(({ value, label, icon: Icon }) => (
            <button
              key={value}
              onClick={() => setTheme(value)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg border text-sm transition-colors ${
                theme === value
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-border hover:bg-accent"
              }`}
            >
              <Icon size={14} />
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Account */}
      <div className="rounded-xl border border-border bg-card p-6">
        <h2 className="font-semibold mb-4">Account</h2>
        <div className="space-y-3">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Email</span>
            <span>{user?.email}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Username</span>
            <span>{user?.username}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Account status</span>
            <span className="text-green-500">Active</span>
          </div>
        </div>
      </div>

      {/* API keys notice */}
      <div className="rounded-xl border border-border bg-card p-6">
        <h2 className="font-semibold mb-2">API Configuration</h2>
        <p className="text-sm text-muted-foreground">
          API keys (Anthropic, OpenAI, Reddit) are configured via environment variables in{" "}
          <code className="font-mono text-xs bg-muted px-1 py-0.5 rounded">.env</code>. See{" "}
          <code className="font-mono text-xs bg-muted px-1 py-0.5 rounded">.env.example</code> for all options.
        </p>
      </div>
    </div>
  );
}
