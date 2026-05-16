import { useState, useRef, useEffect } from "react";

const BRAINS = {
  fast: { label: "0.8B Fast", port: 8091, color: "#22d3ee", icon: "⚡" },
  deep: { label: "4B Deep", port: 8090, color: "#a78bfa", icon: "🧠" },
};

function Message({ msg }) {
  const isUser = msg.role === "user";
  const brain = BRAINS[msg.brain];

  return (
    <div style={{ display: "flex", justifyContent: isUser ? "flex-end" : "flex-start", marginBottom: 12 }}>
      <div style={{
        maxWidth: "85%",
        background: isUser ? "#1e293b" : "#0f172a",
        border: `1px solid ${isUser ? "#334155" : brain?.color + "33" || "#334155"}`,
        borderRadius: isUser ? "16px 16px 4px 16px" : "16px 16px 16px 4px",
        padding: "12px 16px",
        position: "relative",
      }}>
        {!isUser && brain && (
          <div style={{ fontSize: 11, color: brain.color, marginBottom: 6, fontWeight: 600, letterSpacing: "0.05em" }}>
            {brain.icon} {brain.label}
            {msg.stats && (
              <span style={{ color: "#64748b", fontWeight: 400, marginLeft: 8 }}>
                {msg.stats.tokPerSec} tok/s · {msg.stats.wall}s · {msg.stats.thinkChars} think chars
              </span>
            )}
          </div>
        )}

        {msg.thinking && (
          <details style={{ marginBottom: 8 }}>
            <summary style={{ fontSize: 11, color: "#64748b", cursor: "pointer", userSelect: "none" }}>
              reasoning ({msg.thinking.length} chars)
            </summary>
            <pre style={{
              fontSize: 11, color: "#475569", whiteSpace: "pre-wrap", wordBreak: "break-word",
              marginTop: 6, padding: "8px 10px", background: "#020617", borderRadius: 6,
              maxHeight: 150, overflow: "auto", border: "1px solid #1e293b",
            }}>
              {msg.thinking}
            </pre>
          </details>
        )}

        <div style={{ color: isUser ? "#e2e8f0" : "#f1f5f9", fontSize: 14, lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
          {msg.content || (msg.loading ? "..." : "(empty response)")}
        </div>
      </div>
    </div>
  );
}

export default function PepperChat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [brain, setBrain] = useState("fast");
  const [loading, setLoading] = useState(false);
  const [system, setSystem] = useState("You are Pepper, a friendly robot assistant in a university lab. Keep responses conversational and brief (2-3 sentences).");
  const [showSystem, setShowSystem] = useState(false);
  const scrollRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  useEffect(() => { inputRef.current?.focus(); }, [brain]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg = { role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    const b = BRAINS[brain];
    const url = `http://localhost:${b.port}/v1/chat/completions`;

    const history = [...messages.filter(m => m.role === "user" || m.role === "assistant").slice(-10), userMsg];
    const apiMessages = [
      { role: "system", content: system },
      ...history.map(m => ({ role: m.role === "user" ? "user" : "assistant", content: m.content })),
    ];

    try {
      const t0 = performance.now();
      const resp = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: apiMessages, max_tokens: 1500 }),
      });
      const data = await resp.json();
      const wall = ((performance.now() - t0) / 1000).toFixed(1);
      const choice = data.choices?.[0];
      const msg = choice?.message || {};
      const timings = data.timings || {};

      setMessages((prev) => [...prev, {
        role: "assistant",
        content: msg.content || "",
        thinking: msg.reasoning_content || null,
        brain,
        stats: {
          tokPerSec: (timings.predicted_per_second || 0).toFixed(0),
          wall,
          thinkChars: (msg.reasoning_content || "").length,
          totalTokens: data.usage?.completion_tokens || 0,
        },
      }]);
    } catch (err) {
      setMessages((prev) => [...prev, {
        role: "assistant",
        content: `Connection error: ${err.message}\n\nIs llama-server running on port ${b.port}?`,
        brain,
        stats: null,
      }]);
    }
    setLoading(false);
  };

  return (
    <div style={{
      width: "100%", height: "100vh", display: "flex", flexDirection: "column",
      background: "#020617", color: "#e2e8f0",
      fontFamily: "'IBM Plex Sans', 'Segoe UI', system-ui, sans-serif",
    }}>
      {/* Header */}
      <div style={{
        padding: "14px 20px", borderBottom: "1px solid #1e293b",
        display: "flex", alignItems: "center", gap: 12, flexShrink: 0,
      }}>
        <div style={{ fontSize: 20, fontWeight: 700, letterSpacing: "-0.02em" }}>
          🤖 Pepper Chat
        </div>

        <div style={{ display: "flex", gap: 4, marginLeft: 16, background: "#0f172a", borderRadius: 8, padding: 3 }}>
          {Object.entries(BRAINS).map(([key, b]) => (
            <button key={key} onClick={() => setBrain(key)} style={{
              padding: "6px 14px", border: "none", borderRadius: 6, cursor: "pointer",
              fontSize: 12, fontWeight: 600, transition: "all 0.15s",
              background: brain === key ? b.color + "22" : "transparent",
              color: brain === key ? b.color : "#64748b",
              outline: brain === key ? `1px solid ${b.color}44` : "none",
            }}>
              {b.icon} {b.label}
            </button>
          ))}
        </div>

        <button onClick={() => setShowSystem(!showSystem)} style={{
          marginLeft: "auto", padding: "6px 12px", background: "#0f172a", border: "1px solid #1e293b",
          borderRadius: 6, color: "#64748b", fontSize: 11, cursor: "pointer",
        }}>
          {showSystem ? "Hide" : "System"} Prompt
        </button>

        <button onClick={() => { setMessages([]); }} style={{
          padding: "6px 12px", background: "#0f172a", border: "1px solid #1e293b",
          borderRadius: 6, color: "#64748b", fontSize: 11, cursor: "pointer",
        }}>
          Clear
        </button>
      </div>

      {/* System prompt editor */}
      {showSystem && (
        <div style={{ padding: "12px 20px", borderBottom: "1px solid #1e293b", background: "#0a0f1a" }}>
          <div style={{ fontSize: 10, color: "#64748b", marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.1em" }}>
            System Prompt (sent with every request)
          </div>
          <textarea
            value={system}
            onChange={(e) => setSystem(e.target.value)}
            rows={4}
            style={{
              width: "100%", background: "#020617", border: "1px solid #1e293b", borderRadius: 6,
              color: "#94a3b8", fontSize: 12, padding: "10px 12px", resize: "vertical",
              fontFamily: "'IBM Plex Mono', monospace", lineHeight: 1.5, outline: "none",
            }}
          />
        </div>
      )}

      {/* Messages */}
      <div ref={scrollRef} style={{ flex: 1, overflow: "auto", padding: "20px 20px 8px" }}>
        {messages.length === 0 && (
          <div style={{ textAlign: "center", color: "#334155", marginTop: 80 }}>
            <div style={{ fontSize: 48, marginBottom: 12 }}>🤖</div>
            <div style={{ fontSize: 15, fontWeight: 500 }}>Start chatting with Pepper</div>
            <div style={{ fontSize: 12, marginTop: 6 }}>
              Using <span style={{ color: BRAINS[brain].color }}>{BRAINS[brain].icon} {BRAINS[brain].label}</span> on port {BRAINS[brain].port}
            </div>
          </div>
        )}
        {messages.map((msg, i) => <Message key={i} msg={msg} />)}
        {loading && (
          <div style={{ display: "flex", gap: 6, padding: "8px 16px", color: BRAINS[brain].color, fontSize: 13 }}>
            <span className="dots" style={{ display: "inline-flex", gap: 3 }}>
              {[0,1,2].map(i => (
                <span key={i} style={{
                  width: 6, height: 6, borderRadius: "50%", background: BRAINS[brain].color,
                  animation: `pulse 1s ease-in-out ${i * 0.15}s infinite`,
                  opacity: 0.4,
                }} />
              ))}
            </span>
            <span style={{ marginLeft: 4, fontSize: 12, color: "#64748b" }}>
              {BRAINS[brain].label} thinking...
            </span>
          </div>
        )}
      </div>

      {/* Input */}
      <div style={{
        padding: "12px 20px 16px", borderTop: "1px solid #1e293b",
        display: "flex", gap: 10, flexShrink: 0,
      }}>
        <input
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); } }}
          placeholder={`Message ${BRAINS[brain].label}...`}
          disabled={loading}
          style={{
            flex: 1, padding: "12px 16px", background: "#0f172a", border: "1px solid #1e293b",
            borderRadius: 10, color: "#f1f5f9", fontSize: 14, outline: "none",
            fontFamily: "inherit",
          }}
        />
        <button
          onClick={sendMessage}
          disabled={loading || !input.trim()}
          style={{
            padding: "12px 20px", borderRadius: 10, border: "none", cursor: "pointer",
            fontSize: 14, fontWeight: 600,
            background: loading || !input.trim() ? "#1e293b" : BRAINS[brain].color,
            color: loading || !input.trim() ? "#475569" : "#020617",
            transition: "all 0.15s",
          }}
        >
          Send
        </button>
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 0.3; transform: scale(0.8); }
          50% { opacity: 1; transform: scale(1.2); }
        }
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #1e293b; border-radius: 3px; }
        input::placeholder { color: #475569; }
      `}</style>
    </div>
  );
}
