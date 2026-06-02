"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

export const metadata = { title: "Reddit" };

export default function RedditPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold capitalize">reddit</h1>
        <p className="text-muted-foreground text-sm mt-1">Manage your reddit data and operations</p>
      </div>
      <div className="rounded-xl border border-border bg-card p-6">
        <p className="text-muted-foreground">
          Reddit module — connect to the backend API using the configured endpoints.
        </p>
      </div>
    </div>
  );
}
