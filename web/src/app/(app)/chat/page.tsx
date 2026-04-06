"use client";

import { useEffect, useRef } from "react";
import { useChatStore } from "@/stores/chat-store";
import { Header } from "@/components/layout/header";
import { ContextPanel } from "@/components/layout/context-panel";
import { MessageList } from "@/components/chat/message-list";
import { MessageInput } from "@/components/chat/message-input";

export default function ChatPage() {
  const { messages, isTyping, isConnected, connect, disconnect, sendMessage } =
    useChatStore();
  const connectionRef = useRef(false);

  useEffect(() => {
    // Prevent double connection in Strict Mode
    if (connectionRef.current) return;
    connectionRef.current = true;

    connect();

    return () => {
      connectionRef.current = false;
      disconnect();
    };
  }, []); // Empty deps - only run once

  return (
    <div className="flex flex-1 overflow-hidden">
      <div className="flex-1 flex flex-col">
        <Header title="Chat" />

        <MessageList messages={messages} isTyping={isTyping} />

        <MessageInput onSend={sendMessage} disabled={isTyping} />
      </div>

      <ContextPanel />
    </div>
  );
}
