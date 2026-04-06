import { create } from "zustand";
import { chatApi } from "@/lib/api";
import { WebSocketClient, WebSocketMessage } from "@/lib/websocket";

// Module-level singleton WebSocket client
let singletonClient: WebSocketClient | null = null;
let singletonSessionId: string | null = null;

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  realm?: string;
  timestamp: string;
  isStreaming?: boolean;
}

interface ChatState {
  messages: Message[];
  currentRealm: string | null;
  realmFlow: {
    assess: number;
    decide: number;
    do: number;
  };
  isTyping: boolean;
  isConnecting: boolean;
  isConnected: boolean;
  sessionId: string;
  wsClient: WebSocketClient | null;

  // Actions
  connect: (sessionId?: string) => Promise<void>;
  disconnect: () => void;
  forceDisconnect: () => void;
  sendMessage: (content: string) => Promise<void>;
  clearMessages: () => void;
  setSessionId: (sessionId: string) => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  currentRealm: null,
  realmFlow: { assess: 0, decide: 0, do: 0 },
  isTyping: false,
  isConnecting: false,
  isConnected: false,
  sessionId: "default",
  wsClient: null,

  connect: async (sessionId = "default") => {
    // Use module-level singleton to survive React Strict Mode
    if (singletonClient) {
      if (singletonSessionId === sessionId) {
        console.log("Reusing existing singleton connection");
        set({ wsClient: singletonClient, isConnected: true, sessionId });
        return;
      }
      // Different session, disconnect old one
      singletonClient.disconnect();
      singletonClient = null;
      singletonSessionId = null;
    }

    set({ isConnecting: true });

    const client = new WebSocketClient(sessionId);

    // Set singleton BEFORE await to prevent race conditions
    singletonClient = client;
    singletonSessionId = sessionId;

    // Set up handlers
    client.on("chat_message", (data: WebSocketMessage) => {
      const { messages } = get();

      if (data.is_streaming && !data.is_complete) {
        // Streaming: update last message or create new
        const lastMsg = messages[messages.length - 1];
        if (lastMsg?.isStreaming) {
          set({
            messages: [
              ...messages.slice(0, -1),
              { ...lastMsg, content: lastMsg.content + (data.content || "") },
            ],
          });
        } else {
          const newMsg: Message = {
            id: `msg_${Date.now()}`,
            role: "assistant",
            content: data.content || "",
            realm: data.realm,
            timestamp: data.timestamp || new Date().toISOString(),
            isStreaming: true,
          };
          set({ messages: [...messages, newMsg] });
        }
      } else {
        // Complete message
        const lastMsg = messages[messages.length - 1];
        if (lastMsg?.isStreaming) {
          set({
            messages: [
              ...messages.slice(0, -1),
              { ...lastMsg, content: data.content || lastMsg.content, isStreaming: false },
            ],
          });
        } else {
          // Deduplicate: check if same content was just added
          const content = data.content || "";
          const isDuplicate = messages.some(
            (m) => m.role === "assistant" && m.content === content &&
            Date.now() - new Date(m.timestamp).getTime() < 2000
          );
          if (!isDuplicate) {
            const newMsg: Message = {
              id: `msg_${Date.now()}_${Math.random().toString(36).slice(2)}`,
              role: "assistant",
              content,
              realm: data.realm,
              timestamp: data.timestamp || new Date().toISOString(),
            };
            set({ messages: [...messages, newMsg] });
          }
        }
      }

      if (data.realm) {
        set({ currentRealm: data.realm });
      }
    });

    client.on("typing", (data: WebSocketMessage) => {
      set({ isTyping: data.is_typing === true });
    });

    client.on("realm_change", (data: WebSocketMessage) => {
      set({ currentRealm: data.realm || null });
    });

    try {
      await client.connect();
      set({ wsClient: client, isConnected: true, isConnecting: false, sessionId });
    } catch (error) {
      console.error("Failed to connect WebSocket:", error);
      // Clear singleton on failure
      if (singletonClient === client) {
        singletonClient = null;
        singletonSessionId = null;
      }
      set({ isConnected: false, isConnecting: false });
    }
  },

  disconnect: () => {
    // Don't actually disconnect singleton in React Strict Mode cleanup
    // Just update local state - singleton persists
    set({ wsClient: null, isConnected: false, isConnecting: false });
  },

  forceDisconnect: () => {
    // Actually disconnect (for logout, etc.)
    if (singletonClient) {
      singletonClient.disconnect();
      singletonClient = null;
      singletonSessionId = null;
    }
    set({ wsClient: null, isConnected: false, isConnecting: false });
  },

  sendMessage: async (content: string) => {
    const { wsClient, messages, sessionId } = get();

    // Add user message
    const userMsg: Message = {
      id: `msg_${Date.now()}`,
      role: "user",
      content,
      timestamp: new Date().toISOString(),
    };
    set({ messages: [...messages, userMsg] });

    if (wsClient?.isConnected) {
      // Send via WebSocket
      wsClient.sendMessage(content);
    } else {
      // Fall back to REST API
      try {
        set({ isTyping: true });
        const response = await chatApi.sendMessage(content, sessionId);

        const assistantMsg: Message = {
          id: `msg_${Date.now()}`,
          role: "assistant",
          content: response.content,
          realm: response.realm,
          timestamp: response.timestamp,
        };

        set((state) => ({
          messages: [...state.messages, assistantMsg],
          currentRealm: response.realm || state.currentRealm,
          isTyping: false,
        }));
      } catch (error) {
        console.error("Failed to send message:", error);
        set({ isTyping: false });
      }
    }
  },

  clearMessages: () => {
    set({ messages: [] });
  },

  setSessionId: (sessionId: string) => {
    set({ sessionId });
  },
}));
