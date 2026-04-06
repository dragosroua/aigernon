type MessageHandler = (data: WebSocketMessage) => void;

export interface WebSocketMessage {
  type: string;
  content?: string;
  realm?: string;
  is_streaming?: boolean;
  is_complete?: boolean;
  timestamp?: string;
  is_typing?: boolean;
  [key: string]: unknown;
}

function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  const match = document.cookie.match(/auth_token=([^;]+)/);
  return match ? match[1] : null;
}

export class WebSocketClient {
  private ws: WebSocket | null = null;
  private url: string;
  private sessionId: string;
  private handlers: Map<string, Set<MessageHandler>> = new Map();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private pingInterval: ReturnType<typeof setInterval> | null = null;

  constructor(sessionId: string = "default") {
    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";
    const token = getAuthToken();
    this.url = `${wsUrl}/chat/ws?session_id=${sessionId}${token ? `&token=${token}` : ""}`;
    this.sessionId = sessionId;
  }

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(this.url);

        this.ws.onopen = () => {
          console.log("WebSocket connected");
          this.reconnectAttempts = 0;
          this.startPing();
          resolve();
        };

        this.ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data) as WebSocketMessage;
            this.handleMessage(data);
          } catch (e) {
            console.error("Failed to parse WebSocket message:", e);
          }
        };

        this.ws.onclose = (event) => {
          console.log("WebSocket disconnected:", event.code);
          this.stopPing();
          if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnect();
          }
        };

        this.ws.onerror = (error) => {
          console.error("WebSocket error:", error);
          reject(error);
        };
      } catch (error) {
        reject(error);
      }
    });
  }

  disconnect(): void {
    this.stopPing();
    if (this.ws) {
      this.ws.close(1000);
      this.ws = null;
    }
  }

  private reconnect(): void {
    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
    console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
    setTimeout(() => this.connect(), delay);
  }

  private startPing(): void {
    this.pingInterval = setInterval(() => {
      this.send({ type: "ping" });
    }, 30000);
  }

  private stopPing(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  private handleMessage(data: WebSocketMessage): void {
    const handlers = this.handlers.get(data.type);
    if (handlers) {
      handlers.forEach((handler) => handler(data));
    }

    // Also call "all" handlers
    const allHandlers = this.handlers.get("*");
    if (allHandlers) {
      allHandlers.forEach((handler) => handler(data));
    }
  }

  on(type: string, handler: MessageHandler): () => void {
    if (!this.handlers.has(type)) {
      this.handlers.set(type, new Set());
    }
    this.handlers.get(type)!.add(handler);

    // Return unsubscribe function
    return () => {
      this.handlers.get(type)?.delete(handler);
    };
  }

  off(type: string, handler: MessageHandler): void {
    this.handlers.get(type)?.delete(handler);
  }

  send(data: object): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  sendMessage(content: string): void {
    this.send({ type: "message", content });
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}
