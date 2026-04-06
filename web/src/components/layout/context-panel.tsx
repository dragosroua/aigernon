"use client";

import { useChatStore } from "@/stores/chat-store";
import { RealmChart } from "@/components/realm/realm-chart";

export function ContextPanel() {
  const { realmFlow, messages } = useChatStore();

  // Calculate rough realm distribution from messages
  const realmCounts = messages.reduce(
    (acc, msg) => {
      if (msg.realm) {
        acc[msg.realm as keyof typeof acc] = (acc[msg.realm as keyof typeof acc] || 0) + 1;
      }
      return acc;
    },
    { assess: 0, decide: 0, do: 0 }
  );

  const hasRealmData =
    realmFlow.assess > 0 || realmFlow.decide > 0 || realmFlow.do > 0;

  return (
    <aside className="w-64 border-l border-border bg-muted/50 p-4 hidden lg:block">
      <div className="space-y-6">
        {/* Today's Flow */}
        <div>
          <h3 className="text-sm font-medium mb-3">Today&apos;s Flow</h3>
          {hasRealmData ? (
            <RealmChart
              assess={realmFlow.assess}
              decide={realmFlow.decide}
              do={realmFlow.do}
            />
          ) : (
            <p className="text-sm text-muted-foreground">
              Start a conversation to see your realm flow.
            </p>
          )}
        </div>

        {/* Session Stats */}
        <div>
          <h3 className="text-sm font-medium mb-3">This Session</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Messages</span>
              <span>{messages.length}</span>
            </div>
            {Object.entries(realmCounts).map(([realm, count]) =>
              count > 0 ? (
                <div key={realm} className="flex justify-between">
                  <span className="text-muted-foreground capitalize">{realm}</span>
                  <span>{count}</span>
                </div>
              ) : null
            )}
          </div>
        </div>

        {/* Quick Tips */}
        <div>
          <h3 className="text-sm font-medium mb-3">Quick Tips</h3>
          <div className="text-sm text-muted-foreground space-y-2">
            <p>
              🔴 <strong>Assess</strong>: Explore options, ask &quot;what if?&quot;
            </p>
            <p>
              🟠 <strong>Decide</strong>: Make commitments, prioritize
            </p>
            <p>
              🟢 <strong>Do</strong>: Execute, ship, complete
            </p>
          </div>
        </div>
      </div>
    </aside>
  );
}
