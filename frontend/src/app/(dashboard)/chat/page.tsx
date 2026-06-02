import type { Metadata } from "next";
import JarvisChat from "@/components/chat/JarvisChat";

export const metadata: Metadata = { title: "JARVIS Chat" };

export default function ChatPage() {
  return (
    <div className="h-[calc(100vh-6rem)]">
      <JarvisChat />
    </div>
  );
}
