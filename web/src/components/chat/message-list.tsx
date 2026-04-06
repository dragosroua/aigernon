"use client";

import { useEffect, useRef } from "react";
import { cn, formatTime } from "@/lib/utils";
import { Message } from "@/stores/chat-store";
import { RealmBadge } from "@/components/realm/realm-badge";

interface MessageListProps {
  messages: Message[];
  isTyping: boolean;
}

export function MessageList({ messages, isTyping }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
      {messages.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground">
          <h2 className="text-xl font-semibold mb-2">Welcome to AIGernon</h2>
          <p>Your cognitive companion. What&apos;s on your mind?</p>
        </div>
      ) : (
        messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))
      )}

      {isTyping && <TypingIndicator />}

      <div ref={bottomRef} />
    </div>
  );
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";

  return (
    <div
      className={cn("flex", {
        "justify-end": isUser,
        "justify-start": !isUser,
      })}
    >
      <div
        className={cn("max-w-[80%] rounded-2xl px-4 py-3", {
          "bg-primary text-primary-foreground": isUser,
          "bg-muted": !isUser,
        })}
      >
        {!isUser && message.realm && (
          <div className="mb-2">
            <RealmBadge realm={message.realm} size="sm" />
          </div>
        )}

        <div className={cn("prose prose-sm max-w-none", { "prose-invert": isUser })}>
          <p className="whitespace-pre-wrap m-0">{message.content}</p>
        </div>

        <div
          className={cn("text-xs mt-2 opacity-60", {
            "text-right": isUser,
          })}
        >
          {formatTime(message.timestamp)}
          {message.isStreaming && " ..."}
        </div>
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex justify-start">
      <div className="bg-muted rounded-2xl px-4 py-3">
        <div className="flex space-x-1">
          <span className="typing-dot w-2 h-2 rounded-full bg-muted-foreground" />
          <span className="typing-dot w-2 h-2 rounded-full bg-muted-foreground" />
          <span className="typing-dot w-2 h-2 rounded-full bg-muted-foreground" />
        </div>
      </div>
    </div>
  );
}
