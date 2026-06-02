"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { memoryApi } from "@/lib/api";
import { formatRelativeTime, capitalize } from "@/lib/utils";
import { toast } from "sonner";
import { Brain, Plus, Search, Pin, Archive, Trash2, Loader2 } from "lucide-react";
import type { Memory, PaginatedResponse } from "@/types";

export default function MemoryPage() {
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<Array<{ memory: Memory; relevance_score: number }> | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newMemory, setNewMemory] = useState({ title: "", content: "", memory_type: "note" });

  const { data, isLoading } = useQuery<PaginatedResponse<Memory>>({
    queryKey: ["memories"],
    queryFn: () => memoryApi.list(),
  });

  const storeMutation = useMutation({
    mutationFn: () => memoryApi.store(newMemory),
    onSuccess: () => {
      toast.success("Memory stored");
      setNewMemory({ title: "", content: "", memory_type: "note" });
      setShowAddForm(false);
      queryClient.invalidateQueries({ queryKey: ["memories"] });
    },
    onError: () => toast.error("Failed to store memory"),
  });

  const deleteMutation = useMutation({
    mutationFn: memoryApi.delete,
    onSuccess: () => {
      toast.success("Memory deleted");
      queryClient.invalidateQueries({ queryKey: ["memories"] });
    },
  });

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setIsSearching(true);
    try {
      const results = await memoryApi.search({ query: searchQuery, limit: 10 });
      setSearchResults(results);
    } catch {
      toast.error("Search failed");
    } finally {
      setIsSearching(false);
    }
  };

  const MEMORY_TYPES = ["note", "insight", "fact", "decision", "research", "preference", "conversation"];

  const displayItems = searchResults ? searchResults.map((r) => r.memory) : data?.items ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Brain size={24} className="text-purple-500" />
          <div>
            <h1 className="text-2xl font-bold">Memory Vault</h1>
            <p className="text-muted-foreground text-sm">Long-term semantic memory with vector search</p>
          </div>
        </div>
        <button
          onClick={() => setShowAddForm(!showAddForm)}
          className="flex items-center gap-2 px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
        >
          <Plus size={14} />
          Store Memory
        </button>
      </div>

      {/* Search */}
      <div className="flex gap-2">
        <input
          value={searchQuery}
          onChange={(e) => { setSearchQuery(e.target.value); if (!e.target.value) setSearchResults(null); }}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          placeholder="Semantic search across all memories…"
          className="flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        />
        <button
          onClick={handleSearch}
          disabled={isSearching || !searchQuery.trim()}
          className="flex items-center gap-2 px-4 py-2 rounded-md bg-secondary text-secondary-foreground text-sm font-medium hover:bg-secondary/80 disabled:opacity-50 transition-colors"
        >
          {isSearching ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
          Search
        </button>
      </div>

      {/* Add form */}
      {showAddForm && (
        <div className="rounded-xl border border-border bg-card p-6 space-y-4">
          <h2 className="font-semibold">New Memory</h2>
          <input
            value={newMemory.title}
            onChange={(e) => setNewMemory((m) => ({ ...m, title: e.target.value }))}
            placeholder="Title"
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
          <textarea
            value={newMemory.content}
            onChange={(e) => setNewMemory((m) => ({ ...m, content: e.target.value }))}
            placeholder="Memory content…"
            rows={4}
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring resize-none"
          />
          <div className="flex gap-3">
            <select
              value={newMemory.memory_type}
              onChange={(e) => setNewMemory((m) => ({ ...m, memory_type: e.target.value }))}
              className="rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            >
              {MEMORY_TYPES.map((t) => <option key={t} value={t}>{capitalize(t)}</option>)}
            </select>
            <button
              onClick={() => storeMutation.mutate()}
              disabled={!newMemory.title || !newMemory.content || storeMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
            >
              {storeMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : "Save"}
            </button>
          </div>
        </div>
      )}

      {/* Memory list */}
      <div className="grid gap-3">
        {isLoading ? (
          <div className="p-8 text-center text-muted-foreground text-sm">Loading…</div>
        ) : !displayItems.length ? (
          <div className="p-8 text-center rounded-xl border border-border text-muted-foreground text-sm">
            {searchResults !== null ? "No memories matched your search." : "No memories yet. Start storing knowledge."}
          </div>
        ) : (
          displayItems.map((memory) => (
            <div key={memory.id} className="rounded-xl border border-border bg-card p-4 hover:bg-accent/20 transition-colors">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    {memory.is_pinned && <Pin size={12} className="text-yellow-500" />}
                    <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
                      {capitalize(memory.memory_type)}
                    </span>
                  </div>
                  <p className="font-medium text-sm">{memory.title}</p>
                  <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{memory.content}</p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="text-xs text-muted-foreground">{formatRelativeTime(memory.created_at)}</span>
                  <button
                    onClick={() => deleteMutation.mutate(memory.id)}
                    className="text-muted-foreground hover:text-destructive transition-colors"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
