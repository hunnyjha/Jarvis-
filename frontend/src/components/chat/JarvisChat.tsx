"use client";

import { useState, useRef, useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import { agentApi } from "@/lib/api";
import { formatRelativeTime } from "@/lib/utils";
import { Bot, User, Send, Loader2, X } from "lucide-react";
import { toast } from "sonner";
import type { ChatResponse } from "@/types";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  agent?: string;
  processingMs?: number;
}

interface JarvisChatProps {
  onClose?: () => void;
}

export default function JarvisChat({ onClose }: JarvisChatProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "JARVIS online. I'm your personal intelligence operating system.\n\nI can analyze subreddits, conduct research, investigate accounts, help with strategy, and remember everything we discuss.\n\nWhat would you like to work on?",
      timestamp: new Date(),
      agent: "system",
    },
  ]);
  const [input, setInput] = useState("");
  const [conversationId, setConversationId] = useState<string | undefined>();
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const chatMutation = useMutation<ChatResponse, Error, string>({
    mutationFn: (message: string) => agentApi.chat(message, conversationId),
    onSuccess: (data) => {
      if (!conversationId) setConversationId(data.conversation_id);
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: data.message,
          timestamp: new Date(),
          agent: data.agent_used,
          processingMs: data.processing_time_ms,
        },
      ]);
    },
    onError: () => {
      toast.error("JARVIS encountered an error");
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: "I encountered an error processing your request. Please try again.",
          timestamp: new Date(),
          agent: "error",
        },
      ]);
    },
  });

  const sendMessage = () => {
    const text = input.trim();
    if (!text || chatMutation.isPending) return;

    setMessages((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        role: "user",
        content: text,
        timestamp: new Date(),
      },
    ]);
    setInput("");
    chatMutation.mutate(text);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    e.target.style.height = "auto";
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + "px";
  };

  const AGENT_COLORS: Record<string, string> = {
    reddit_agent: "text-orange-400",
    research_agent: "text-blue-400",
    security_agent: "text-red-400",
    strategy_agent: "text-purple-400",
    memory_agent: "text-green-400",
    chat_agent: "text-primary",
    orchestrator: "text-primary",
    system: "text-muted-foreground",
  };

  return (
    <div className="flex flex-col h-full bg-card rounded-xl border border-border overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          <span className="font-semibold text-sm">JARVIS</span>
          <span className="text-xs text-muted-foreground">Intelligence OS</span>
        </div>
        {onClose && (
          <button onClick={onClose} className="p-1 hover:bg-accent rounded transition-colors">
            <X size={14} />
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex items-start gap-3 ${msg.role === "user" ? "flex-row-reverse" : ""}`}
          >
            <div
              className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 ${
                msg.role === "user" ? "bg-primary" : "bg-muted"
              }`}
            >
              {msg.role === "user" ? (
                <User size={14} className="text-primary-foreground" />
              ) : (
                <Bot size={14} className="text-muted-foreground" />
              )}
            </div>
            <div
              className={`max-w-[80%] ${msg.role === "user" ? "items-end" : "items-start"} flex flex-col gap-1`}
            >
              <div
                className={`rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
                  msg.role === "user"
                    ? "bg-primary text-primary-foreground rounded-tr-sm"
                    : "bg-muted text-foreground rounded-tl-sm"
                }`}
              >
                {msg.content}
              </div>
              <div className="flex items-center gap-2 text-xs text-muted-foreground px-1">
                <span>{msg.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                {msg.agent && msg.agent !== "system" && (
                  <span className={AGENT_COLORS[msg.agent] || "text-muted-foreground"}>
                    via {msg.agent.replace("_agent", "").replace("_", " ")}
                  </span>
                )}
                {msg.processingMs && (
                  <span className="text-muted-foreground/50">{msg.processingMs}ms</span>
                )}
              </div>
            </div>
          </div>
        ))}

        {chatMutation.isPending && (
          <div className="flex items-start gap-3">
            <div className="w-7 h-7 rounded-full bg-muted flex items-center justify-center">
              <Bot size={14} className="text-muted-foreground" />
            </div>
            <div className="bg-muted rounded-2xl rounded-tl-sm px-4 py-3">
              <div className="flex gap-1">
                {[0, 1, 2].map((i) => (
                  <div
                    key={i}
                    className="w-1.5 h-1.5 bg-muted-foreground/50 rounded-full animate-bounce"
                    style={{ animationDelay: `${i * 150}ms` }}
                  />
                ))}
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="p-3 border-t border-border">
        <div className="flex items-end gap-2 rounded-xl border border-input bg-background px-3 py-2 focus-within:ring-2 focus-within:ring-ring">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={handleTextareaChange}
            onKeyDown={handleKeyDown}
            placeholder="Ask JARVIS anything…"
            rows={1}
            className="flex-1 bg-transparent text-sm resize-none focus:outline-none min-h-[20px] max-h-[120px] scrollbar-thin"
            disabled={chatMutation.isPending}
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || chatMutation.isPending}
            className="p-1.5 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shrink-0"
          >
            {chatMutation.isPending ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Send size={14} />
            )}
          </button>
        </div>
        <p className="text-xs text-muted-foreground text-center mt-1.5">
          Enter to send · Shift+Enter for new line
        </p>
      </div>
    </div>
  );
}
