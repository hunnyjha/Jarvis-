"use client";

import { useAuthStore } from "@/store/authStore";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

export function useRequireAuth() {
  const { isAuthenticated, isLoading } = useAuthStore();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login");
    }
  }, [isAuthenticated, isLoading, router]);

  return { isAuthenticated, isLoading };
}

export function useCurrentUser() {
  const { user, isAuthenticated } = useAuthStore();
  return { user, isAuthenticated };
}
