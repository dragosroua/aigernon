"use client";

import { useEffect, useState } from "react";
import { memoryApi, TodayMemory, SearchResult } from "@/lib/api";
import { Header } from "@/components/layout/header";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Search, AlertCircle } from "lucide-react";

export default function MemoryPage() {
  const [todayMemory, setTodayMemory] = useState<TodayMemory | null>(null);
  const [longTermMemory, setLongTermMemory] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"today" | "longterm" | "search">("today");

  useEffect(() => {
    loadMemory();
  }, []);

  const loadMemory = async () => {
    try {
      const [today, longTerm] = await Promise.all([
        memoryApi.getToday(),
        memoryApi.getLongTerm(),
      ]);
      setTodayMemory(today);
      setLongTermMemory(longTerm.content);
    } catch (error) {
      console.error("Failed to load memory:", error);
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;

    try {
      setIsSearching(true);
      setSearchError(null);
      setActiveTab("search");
      const data = await memoryApi.search(searchQuery);
      setSearchResults(data.results);
    } catch (error) {
      console.error("Search failed:", error);
      const errorMessage = error instanceof Error ? error.message : "Search failed";
      // Check for common vector DB errors
      if (errorMessage.includes("vector") || errorMessage.includes("not available") || errorMessage.includes("ChromaDB")) {
        setSearchError("Vector search is not available. The vector database may not be configured or running.");
      } else {
        setSearchError(errorMessage);
      }
      setSearchResults([]);
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col">
      <Header title="Memory" />

      <div className="p-6 flex-1 overflow-auto">
        {/* Search */}
        <div className="flex gap-2 mb-6">
          <Input
            placeholder="Search your memory..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          />
          <Button onClick={handleSearch} disabled={isSearching}>
            <Search className="h-4 w-4" />
          </Button>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-4 border-b border-border">
          <button
            onClick={() => setActiveTab("today")}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
              activeTab === "today"
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground"
            }`}
          >
            Today
          </button>
          <button
            onClick={() => setActiveTab("longterm")}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
              activeTab === "longterm"
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground"
            }`}
          >
            Long-term
          </button>
          {(searchResults.length > 0 || searchError) && (
            <button
              onClick={() => setActiveTab("search")}
              className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
                activeTab === "search"
                  ? "border-primary text-primary"
                  : "border-transparent text-muted-foreground"
              }`}
            >
              Search Results {searchResults.length > 0 && `(${searchResults.length})`}
            </button>
          )}
        </div>

        {/* Content */}
        <div className="prose prose-sm max-w-none dark:prose-invert">
          {activeTab === "today" && (
            <div>
              <h2>Today - {todayMemory?.date}</h2>
              {todayMemory?.has_content ? (
                <pre className="whitespace-pre-wrap bg-muted p-4 rounded-lg">
                  {todayMemory.content}
                </pre>
              ) : (
                <p className="text-muted-foreground">No memory entries for today yet.</p>
              )}
            </div>
          )}

          {activeTab === "longterm" && (
            <div>
              <h2>Long-term Memory</h2>
              {longTermMemory ? (
                <pre className="whitespace-pre-wrap bg-muted p-4 rounded-lg">
                  {longTermMemory}
                </pre>
              ) : (
                <p className="text-muted-foreground">No long-term memory entries.</p>
              )}
            </div>
          )}

          {activeTab === "search" && (
            <div>
              <h2>Search Results</h2>
              {searchError ? (
                <div className="p-4 rounded-lg border-2 border-yellow-500/50 bg-yellow-500/10">
                  <div className="flex items-start gap-3">
                    <AlertCircle className="h-5 w-5 text-yellow-500 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="font-medium text-yellow-500 m-0">Search Unavailable</p>
                      <p className="text-sm text-muted-foreground mt-1 m-0">{searchError}</p>
                      <p className="text-xs text-muted-foreground mt-2 m-0">
                        You can still browse Today and Long-term memory above.
                      </p>
                    </div>
                  </div>
                </div>
              ) : searchResults.length === 0 ? (
                <p className="text-muted-foreground">No results found.</p>
              ) : (
                <div className="space-y-4">
                  {searchResults.map((result, i) => (
                    <div key={i} className="p-4 bg-muted rounded-lg">
                      <div className="flex justify-between items-start mb-2">
                        {result.title && (
                          <h3 className="font-medium m-0">{result.title}</h3>
                        )}
                        <span className="text-xs text-muted-foreground">
                          Score: {(result.score * 100).toFixed(0)}%
                        </span>
                      </div>
                      <p className="text-sm m-0">{result.text}</p>
                      {result.source && (
                        <p className="text-xs text-muted-foreground mt-2 m-0">
                          Source: {result.source}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
