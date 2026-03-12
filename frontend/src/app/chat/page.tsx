"use client";

import { useState, useRef, useEffect } from "react";
import { useGender } from "@/hooks/useGender";
import { Send, Sparkles, Trophy, TrendingUp, AlertTriangle, Loader2 } from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Message {
  role: "user" | "assistant";
  content: string;
}

function renderMarkdown(text: string) {
  // Split into lines and process
  return text.split("\n").map((line, li) => {
    // Bold: **text**
    const parts = line.split(/(\*\*[^*]+\*\*)/g).map((part, pi) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return <strong key={pi} className="font-semibold">{part.slice(2, -2)}</strong>;
      }
      return <span key={pi}>{part}</span>;
    });

    // Bullet points
    if (line.startsWith("- ")) {
      return <div key={li} className="flex gap-1.5 ml-1"><span className="text-accent">&#8226;</span><span>{parts.slice(0)}</span></div>;
    }

    return <div key={li} className={line === "" ? "h-2" : ""}>{parts}</div>;
  });
}

const suggestedQuestions = [
  { icon: Trophy, text: "Compare Duke and Houston — who has the edge?" },
  { icon: TrendingUp, text: "Best Cinderella pick this year?" },
  { icon: AlertTriangle, text: "What makes the SEC the strongest conference?" },
  { icon: Sparkles, text: "How does the prediction model work?" },
];

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        "Hey! I'm the Madness Agent — your bracket advisor powered by our prediction model. I can look up any D1 team's stats, compare head-to-head matchups with win probabilities, analyze conferences, check live scores, and find upset candidates.\n\nI can also explain how the app works — Elo ratings, the prediction model, strength of schedule, anything.\n\nWhat would you like to know?",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [gender, setGender] = useGender();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async (text?: string) => {
    const userMsg = (text || input).trim();
    if (!userMsg || loading) return;
    setInput("");

    const newMessages: Message[] = [...messages, { role: "user", content: userMsg }];
    setMessages([...newMessages, { role: "assistant", content: "" }]);
    setLoading(true);

    try {
      // Send only last 10 messages to keep token usage low
      const historyToSend = newMessages
        .filter((m) => m.role === "user" || m.role === "assistant")
        .slice(-10);

      const res = await fetch(`${API_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: historyToSend, gender }),
      });

      if (!res.ok) {
        if (res.status === 429) {
          throw new Error("You've hit the rate limit. Please wait a few minutes before sending more messages.");
        }
        const err = await res.text();
        throw new Error(err || `HTTP ${res.status}`);
      }

      const reader = res.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let assistantText = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split("\n");

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = line.slice(6);
            if (data === "[DONE]") break;
            try {
              const parsed = JSON.parse(data);
              if (parsed.text) {
                assistantText += parsed.text;
                setMessages((prev) => {
                  const updated = [...prev];
                  updated[updated.length - 1] = {
                    role: "assistant",
                    content: assistantText,
                  };
                  return updated;
                });
              }
            } catch {
              // skip malformed chunks
            }
          }
        }
      }
    } catch (err) {
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          role: "assistant",
          content: `Sorry, I ran into an error: ${err instanceof Error ? err.message : "Unknown error"}. Please try again.`,
        };
        return updated;
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col max-w-3xl mx-auto px-4 sm:px-6">
      {/* Header */}
      <div className="py-8">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-accent/10 flex items-center justify-center">
              <Sparkles className="text-accent" size={20} />
            </div>
            <div>
              <h1 className="text-2xl font-bold">Madness Agent</h1>
              <p className="text-muted text-sm">
                Bracket advisor grounded in model predictions
              </p>
            </div>
          </div>
          <div className="flex gap-1 bg-card border border-card-border rounded-lg p-1">
            <button
              onClick={() => setGender("M")}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                gender === "M" ? "bg-accent text-white" : "text-muted hover:text-foreground"
              }`}
            >
              Men
            </button>
            <button
              onClick={() => setGender("W")}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                gender === "W" ? "bg-accent text-white" : "text-muted hover:text-foreground"
              }`}
            >
              Women
            </button>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 space-y-4 pb-4">
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] px-4 py-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${
                msg.role === "user"
                  ? "bg-accent text-white rounded-br-md"
                  : "bg-card border border-card-border rounded-bl-md"
              }`}
            >
              {msg.content
                ? msg.role === "assistant"
                  ? renderMarkdown(msg.content)
                  : msg.content
                : loading && i === messages.length - 1 && (
                    <Loader2 size={16} className="animate-spin text-muted" />
                  )}
            </div>
          </div>
        ))}

        {/* Suggested questions */}
        {messages.length === 1 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-4">
            {suggestedQuestions.map((q) => {
              const Icon = q.icon;
              return (
                <button
                  key={q.text}
                  onClick={() => handleSend(q.text)}
                  className="flex items-center gap-2 p-3 rounded-xl bg-card border border-card-border hover:border-accent/30 text-sm text-left transition-colors"
                >
                  <Icon size={14} className="text-accent shrink-0" />
                  <span className="text-muted">{q.text}</span>
                </button>
              );
            })}
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="sticky bottom-0 py-4 bg-background">
        <div className="flex items-center gap-2 p-2 bg-card border border-card-border rounded-xl">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder="Ask about matchups, upsets, or bracket strategy..."
            className="flex-1 px-3 py-2 bg-transparent text-foreground placeholder:text-muted focus:outline-none text-sm"
            disabled={loading}
          />
          <button
            onClick={() => handleSend()}
            disabled={!input.trim() || loading}
            className="p-2 rounded-lg bg-accent text-white disabled:opacity-30 hover:bg-accent-secondary transition-colors"
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
          </button>
        </div>
        <p className="text-xs text-muted text-center mt-2">
          Data: Kaggle March ML Mania &middot; Live: ESPN &middot; Predictions: Elo + LightGBM ensemble
        </p>
      </div>
    </div>
  );
}
