import React, { useState, useRef, useEffect, useCallback } from 'react';
import { usePepperStore } from '../hooks/usePepperState';

const BRIDGE_URL = 'http://localhost:5001';

function ChatPopup() {
  const [open, setOpen] = useState(() => {
    try { return JSON.parse(localStorage.getItem('chat_open') ?? 'true'); }
    catch { return true; }
  });
  const [minimized, setMinimized] = useState(false);
  const [position, setPosition] = useState(() => {
    try { return JSON.parse(localStorage.getItem('chat_pos')) || { x: null, y: null }; }
    catch { return { x: null, y: null }; }
  });
  const [input, setInput] = useState('');
  const messages = usePepperStore((s) => s.chatMessages);
  const chatLoading = usePepperStore((s) => s.chatLoading);
  const addChatMessage = usePepperStore((s) => s.addChatMessage);
  const setChatLoading = usePepperStore((s) => s.setChatLoading);

  const messagesEndRef = useRef(null);
  const dragRef = useRef(null);
  const dragStartRef = useRef(null);

  useEffect(() => {
    localStorage.setItem('chat_open', JSON.stringify(open));
  }, [open]);

  useEffect(() => {
    if (position.x !== null) {
      localStorage.setItem('chat_pos', JSON.stringify(position));
    }
  }, [position]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleDragStart = useCallback((e) => {
    const rect = dragRef.current?.getBoundingClientRect();
    if (!rect) return;
    dragStartRef.current = {
      offsetX: e.clientX - rect.left,
      offsetY: e.clientY - rect.top,
    };
    const handleMove = (ev) => {
      if (!dragStartRef.current) return;
      setPosition({
        x: ev.clientX - dragStartRef.current.offsetX,
        y: ev.clientY - dragStartRef.current.offsetY,
      });
    };
    const handleUp = () => {
      dragStartRef.current = null;
      document.removeEventListener('mousemove', handleMove);
      document.removeEventListener('mouseup', handleUp);
    };
    document.addEventListener('mousemove', handleMove);
    document.addEventListener('mouseup', handleUp);
  }, []);

  const sendMessage = useCallback(async () => {
    const text = input.trim();
    if (!text || chatLoading) return;
    setInput('');
    addChatMessage({ role: 'user', text, ts: Date.now() });
    setChatLoading(true);
    try {
      const res = await fetch(`${BRIDGE_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });
      const data = await res.json();
      addChatMessage({
        role: 'pepper',
        text: data.data?.response ?? data.error ?? 'No response',
        routedTo: data.data?.routed_to,
        ts: Date.now(),
      });
    } catch (err) {
      addChatMessage({ role: 'pepper', text: `Connection error: ${err.message}`, ts: Date.now() });
    } finally {
      setChatLoading(false);
    }
  }, [input, chatLoading, addChatMessage, setChatLoading]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        style={{
          position: 'fixed', bottom: '20px', right: '400px',
          width: '40px', height: '40px', borderRadius: '50%',
          background: '#2c2c2e', border: '1px solid #3a3a3c',
          color: '#e5e5e5', fontSize: '18px', cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 200,
        }}
        title="Open chat"
      >
        C
      </button>
    );
  }

  if (minimized) {
    return (
      <button
        onClick={() => setMinimized(false)}
        style={{
          position: 'fixed',
          bottom: position.y !== null ? undefined : '20px',
          right: position.x !== null ? undefined : '400px',
          top: position.y !== null ? position.y : undefined,
          left: position.x !== null ? position.x : undefined,
          padding: '6px 16px', borderRadius: '20px',
          background: '#2c2c2e', border: '1px solid #3a3a3c',
          color: '#e5e5e5', fontSize: '12px', cursor: 'pointer',
          fontFamily: "-apple-system, 'Segoe UI', Roboto, sans-serif",
          zIndex: 200,
        }}
      >
        Chat {messages.length > 0 ? `(${messages.length})` : ''}
      </button>
    );
  }

  const posStyle = position.x !== null
    ? { top: position.y, left: position.x }
    : { bottom: '20px', right: '400px' };

  return (
    <div
      ref={dragRef}
      style={{
        position: 'fixed',
        ...posStyle,
        width: '320px',
        height: '420px',
        background: '#2c2c2e',
        border: '1px solid #3a3a3c',
        borderRadius: '10px',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        zIndex: 200,
        boxShadow: '0 4px 20px rgba(0,0,0,0.4)',
        fontFamily: "-apple-system, 'Segoe UI', Roboto, sans-serif",
      }}
    >
      {/* Header */}
      <div
        onMouseDown={handleDragStart}
        style={{
          padding: '10px 14px',
          borderBottom: '1px solid #3a3a3c',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          cursor: 'grab',
          userSelect: 'none',
        }}
      >
        <span style={{ fontSize: '13px', fontWeight: 600, color: '#e5e5e5' }}>Chat</span>
        <div style={{ display: 'flex', gap: '8px' }}>
          <span
            onClick={() => setMinimized(true)}
            style={{ cursor: 'pointer', color: '#666', fontSize: '14px' }}
          >—</span>
          <span
            onClick={() => setOpen(false)}
            style={{ cursor: 'pointer', color: '#666', fontSize: '14px' }}
          >✕</span>
        </div>
      </div>

      {/* Messages */}
      <div style={{
        flex: 1, overflowY: 'auto', padding: '10px',
        display: 'flex', flexDirection: 'column', gap: '8px',
      }}>
        {messages.length === 0 && (
          <div style={{ color: '#666', fontSize: '12px', textAlign: 'center', marginTop: '40px' }}>
            Say something to Pepper...
          </div>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            style={{
              alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
              maxWidth: '85%',
            }}
          >
            <div style={{
              padding: '8px 12px',
              borderRadius: msg.role === 'user' ? '10px 10px 4px 10px' : '10px 10px 10px 4px',
              background: msg.role === 'user' ? '#3a3a3c' : '#2a3a2a',
              color: msg.role === 'user' ? '#e5e5e5' : '#8aba8a',
              fontSize: '13px',
              lineHeight: '1.4',
            }}>
              {msg.text}
            </div>
            {msg.routedTo && (
              <div style={{ fontSize: '9px', color: '#666', marginTop: '2px', paddingLeft: '4px' }}>
                via {msg.routedTo}
              </div>
            )}
          </div>
        ))}
        {chatLoading && (
          <div style={{
            alignSelf: 'flex-start',
            padding: '8px 12px',
            borderRadius: '10px 10px 10px 4px',
            background: '#2a3a2a',
            color: '#8aba8a',
            fontSize: '13px',
          }}>
            ...
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div style={{ padding: '10px', borderTop: '1px solid #3a3a3c', display: 'flex', gap: '8px' }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type a message..."
          style={{
            flex: 1,
            padding: '8px 12px',
            background: '#1c1c1e',
            border: '1px solid #3a3a3c',
            borderRadius: '6px',
            color: '#e5e5e5',
            fontSize: '13px',
            outline: 'none',
            fontFamily: 'inherit',
          }}
        />
        <button
          onClick={sendMessage}
          disabled={chatLoading || !input.trim()}
          style={{
            padding: '8px 14px',
            background: chatLoading || !input.trim() ? '#3a3a3c' : '#8aba8a',
            border: 'none',
            borderRadius: '6px',
            color: chatLoading || !input.trim() ? '#666' : '#1c1c1e',
            fontSize: '13px',
            fontWeight: 600,
            cursor: chatLoading || !input.trim() ? 'default' : 'pointer',
          }}
        >
          Send
        </button>
      </div>
    </div>
  );
}

export default ChatPopup;
