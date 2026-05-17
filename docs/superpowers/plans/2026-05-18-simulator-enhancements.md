# 3D Simulator Enhancements — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the 3D Pepper simulator to a warm dark macOS palette and add three features: floating chat popup, chest tablet animations, and web search results display.

**Architecture:** All styling changes are CSS-in-JS (inline styles) matching the existing codebase pattern — no CSS files exist. New features are self-contained React components mounted in `App.jsx`. Backend changes add a `/chat` endpoint to `sim_bridge.py` and a `search_results` field to `sim_state.py`'s WebSocket broadcast. The Zustand store in `usePepperState.js` gets new fields for chat, search results, and derived robot state.

**Tech Stack:** React 18, React Three Fiber, Three.js, Zustand, Vite — no new dependencies.

**Design spec:** `docs/superpowers/specs/2026-05-18-simulator-enhancements-design.md`

---

## File Map

### New files
| File | Responsibility |
|---|---|
| `simulator/web/src/components/ChatPopup.jsx` | Floating draggable chat panel with message state and bridge API calls |
| `simulator/web/src/components/TabletRenderer.js` | Offscreen canvas logic: state animations (idle/speaking/thinking) + content rendering for Pepper's chest tablet texture |
| `simulator/web/src/components/SearchResultPopup.jsx` | Floating auto-dismissing search results overlay (top-right) |

### Modified files
| File | What changes |
|---|---|
| `simulator/web/src/App.jsx` | Restyle to warm dark palette; mount ChatPopup, SearchResultPopup; update SpeechOverlay and StatusBar colors |
| `simulator/web/src/components/Dashboard.jsx` | Restyle all panels/sections to warm dark palette |
| `simulator/web/src/components/Room.jsx` | Neutral lighting colors; designate one desk monitor as "search monitor" with dynamic emissive |
| `simulator/web/src/components/PepperModel.jsx` | Remove blue glow from tablet; integrate TabletRenderer canvas texture on chest mesh |
| `simulator/web/src/hooks/usePepperState.js` | Add `searchResults`, `chatMessages`, `robotState` fields; handle new WebSocket event types |
| `simulator/sim_bridge.py` | Add `POST /chat` endpoint; add `POST /search_results` endpoint for orchestrator to push results |
| `simulator/sim_state.py` | Add `search_results` list + `push_search_result()` method; include in `to_dict()` broadcast |

---

## Task 1: Restyle App.jsx — warm dark palette

**Files:**
- Modify: `simulator/web/src/App.jsx`

The color palette tokens (used as literals in inline styles):
- `#1c1c1e` — page bg, deep surfaces
- `#2c2c2e` — panels, cards, popups
- `#3a3a3c` — borders, elevated surfaces, dividers
- `#e5e5e5` — primary text
- `#999` — secondary text
- `#666` — muted/placeholder text
- `#8aba8a` — positive accent (green)
- `#ba8a8a` — negative accent (red)

- [ ] **Step 1: Restyle the root layout and Canvas background**

Replace the root `div` background and Canvas style from `#0a0a0f` to `#1c1c1e`. Remove the fog's blue tint.

```jsx
// In App() return:
<div style={{ display: 'flex', width: '100vw', height: '100vh', background: '#1c1c1e' }}>
  {/* 3D Viewport */}
  <div style={{ flex: 1, position: 'relative' }}>
    <Canvas
      camera={{ position: [3, 4, 6], fov: 50, near: 0.1, far: 100 }}
      shadows
      gl={{ antialias: true }}
      style={{ background: '#1c1c1e' }}
    >
      {/* ... existing Suspense, OrbitControls ... */}
      <fog attach="fog" args={['#1c1c1e', 8, 20]} />
    </Canvas>
```

- [ ] **Step 2: Restyle StatusBar to warm dark**

Replace the entire `StatusBar` function body. Remove `backdropFilter`, colored borders, green glow shadows. Use the warm palette:

```jsx
function StatusBar() {
  const connected = usePepperStore((s) => s.connected);
  const battery = usePepperStore((s) => s.battery);
  const posture = usePepperStore((s) => s.posture);
  const isMoving = usePepperStore((s) => s.isMoving);

  return (
    <div style={{
      position: 'absolute',
      top: '16px',
      left: '16px',
      display: 'flex',
      gap: '12px',
      alignItems: 'center',
      fontFamily: "'JetBrains Mono', monospace",
      fontSize: '11px',
      zIndex: 100,
      pointerEvents: 'none',
    }}>
      <div style={{
        padding: '6px 12px',
        background: '#2c2c2e',
        border: '1px solid #3a3a3c',
        borderRadius: '6px',
        color: connected ? '#8aba8a' : '#ba8a8a',
      }}>
        {connected ? '● CONNECTED' : '○ DISCONNECTED'}
      </div>

      <div style={{
        padding: '6px 12px',
        background: '#2c2c2e',
        border: '1px solid #3a3a3c',
        borderRadius: '6px',
        color: battery > 50 ? '#8aba8a' : battery > 20 ? '#d4a847' : '#ba8a8a',
      }}>
        {battery}%
      </div>

      <div style={{
        padding: '6px 12px',
        background: '#2c2c2e',
        border: '1px solid #3a3a3c',
        borderRadius: '6px',
        color: '#999',
      }}>
        {posture} {isMoving ? '→' : ''}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Restyle SpeechOverlay to warm dark**

```jsx
function SpeechOverlay() {
  const isSpeaking = usePepperStore((s) => s.isSpeaking);
  const currentSpeech = usePepperStore((s) => s.currentSpeech);
  const speechLanguage = usePepperStore((s) => s.speechLanguage);

  if (!isSpeaking || !currentSpeech) return null;

  return (
    <div style={{
      position: 'absolute',
      bottom: '80px',
      left: '50%',
      transform: 'translateX(-50%)',
      maxWidth: '500px',
      padding: '14px 24px',
      background: 'rgba(44, 44, 46, 0.95)',
      border: '1px solid #3a3a3c',
      borderRadius: '10px',
      fontFamily: "-apple-system, 'Segoe UI', Roboto, sans-serif",
      fontSize: '15px',
      color: '#e5e5e5',
      textAlign: 'center',
      zIndex: 100,
      pointerEvents: 'none',
    }}>
      <div style={{
        fontSize: '9px',
        color: '#999',
        textTransform: 'uppercase',
        letterSpacing: '2px',
        marginBottom: '6px',
      }}>
        Speaking ({speechLanguage})
      </div>
      "{currentSpeech}"
    </div>
  );
}
```

- [ ] **Step 4: Restyle LoadingFallback and title watermark**

```jsx
function LoadingFallback() {
  return (
    <Html center>
      <div style={{
        fontFamily: "-apple-system, 'Segoe UI', Roboto, sans-serif",
        color: '#999',
        fontSize: '18px',
      }}>
        Loading Simulator...
      </div>
    </Html>
  );
}
```

Watermark in App return:
```jsx
<div style={{
  position: 'absolute',
  bottom: '16px',
  left: '16px',
  fontFamily: "-apple-system, 'Segoe UI', Roboto, sans-serif",
  fontSize: '11px',
  color: '#3a3a3c',
  zIndex: 100,
  pointerEvents: 'none',
}}>
  PEPPER AI × SIMULATOR v1.0
</div>
```

- [ ] **Step 5: Verify in browser**

Run: `cd simulator/web && npm run dev`
Open http://localhost:5173. Confirm:
- Page background is warm dark gray, not black
- StatusBar pills are `#2c2c2e` with `#3a3a3c` borders, no glow
- No blue or purple visible anywhere in the App.jsx-controlled elements
- Font is system stack, not Space Grotesk

- [ ] **Step 6: Commit**

```bash
git add simulator/web/src/App.jsx
git commit -m "restyle App.jsx to warm dark macOS palette"
```

---

## Task 2: Restyle Dashboard.jsx

**Files:**
- Modify: `simulator/web/src/components/Dashboard.jsx`

- [ ] **Step 1: Replace the entire styles object**

```jsx
const styles = {
  container: {
    width: '380px',
    height: '100vh',
    background: '#2c2c2e',
    borderLeft: '1px solid #3a3a3c',
    display: 'flex',
    flexDirection: 'column',
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: '11px',
    color: '#999',
    overflow: 'hidden',
  },
  header: {
    padding: '16px 20px',
    borderBottom: '1px solid #3a3a3c',
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
  },
  title: {
    fontFamily: "-apple-system, 'Segoe UI', Roboto, sans-serif",
    fontSize: '16px',
    fontWeight: 700,
    color: '#e5e5e5',
    letterSpacing: '-0.5px',
  },
  statusDot: (connected) => ({
    width: '8px',
    height: '8px',
    borderRadius: '50%',
    background: connected ? '#8aba8a' : '#ba8a8a',
  }),
  section: {
    padding: '12px 20px',
    borderBottom: '1px solid #3a3a3c',
  },
  sectionTitle: {
    fontFamily: "-apple-system, 'Segoe UI', Roboto, sans-serif",
    fontSize: '10px',
    fontWeight: 600,
    color: '#666',
    textTransform: 'uppercase',
    letterSpacing: '1.5px',
    marginBottom: '8px',
  },
  row: {
    display: 'flex',
    justifyContent: 'space-between',
    padding: '2px 0',
  },
  label: {
    color: '#666',
  },
  value: {
    color: '#e5e5e5',
  },
  battery: (level) => ({
    color: level > 50 ? '#8aba8a' : level > 20 ? '#d4a847' : '#ba8a8a',
    fontWeight: 600,
  }),
  speechBox: {
    background: '#1c1c1e',
    borderRadius: '6px',
    padding: '8px 12px',
    marginTop: '4px',
    color: '#e5e5e5',
    fontStyle: 'italic',
    minHeight: '24px',
    wordBreak: 'break-word',
  },
  logContainer: {
    flex: 1,
    overflow: 'auto',
    padding: '12px 20px',
  },
  logEntry: {
    padding: '4px 0',
    borderBottom: '1px solid #1c1c1e',
    display: 'flex',
    gap: '8px',
    fontSize: '10px',
  },
  logTime: {
    color: '#666',
    minWidth: '55px',
  },
  logMethod: (method) => ({
    color: method === 'POST' ? '#d4a847' : '#8aba8a',
    fontWeight: 600,
    minWidth: '32px',
  }),
  logEndpoint: {
    color: '#999',
    flex: 1,
  },
  posIndicator: {
    display: 'flex',
    gap: '16px',
    marginTop: '4px',
  },
  miniMap: {
    width: '100%',
    height: '80px',
    background: '#1c1c1e',
    borderRadius: '6px',
    border: '1px solid #3a3a3c',
    position: 'relative',
    marginTop: '4px',
    overflow: 'hidden',
  },
};
```

- [ ] **Step 2: Update MiniMap SVG colors**

In the `MiniMap` component, update the SVG element colors:

```jsx
{/* Room objects */}
{Object.entries(roomObjects).map(([name, obj]) => (
  <circle
    key={name}
    cx={obj.x * scaleX}
    cy={mapH - obj.y * scaleY}
    r={3}
    fill="#3a3a3c"
  />
))}

{/* Pepper position */}
<circle
  cx={x * scaleX}
  cy={mapH - y * scaleY}
  r={5}
  fill="#8aba8a"
  stroke="#a0cca0"
  strokeWidth={1}
/>

{/* Direction indicator */}
<line
  x1={x * scaleX}
  y1={mapH - y * scaleY}
  x2={x * scaleX + Math.cos(-theta + Math.PI/2) * 12}
  y2={mapH - y * scaleY - Math.sin(-theta + Math.PI/2) * 12}
  stroke="#8aba8a"
  strokeWidth={2}
/>
```

- [ ] **Step 3: Update inline color references in Dashboard component body**

In the `Dashboard` component's JSX, update these inline styles:

1. The LIVE/OFFLINE text: `color: '#666'` (was `#4a4a6a`)
2. The Moving YES: `color: isMoving ? '#8aba8a' : '#666'` (was `#44ff88` / `#6a6a8a`)
3. The Speech speaking indicator: `color: '#8aba8a'` (was `#44ff88`)
4. The Animation text: `color: '#d4a847'` (was `#ffaa44`)
5. The empty log text: `color: '#3a3a3c'` (was `#3a3a5a`)

- [ ] **Step 4: Verify in browser**

Open http://localhost:5173. Confirm:
- Dashboard panel is `#2c2c2e`, not `#0d0d14`
- Section dividers are `#3a3a3c`
- Status dot has no glow/shadow
- MiniMap Pepper dot is green `#8aba8a`, not blue
- Log entries use warm colors, no blue
- Battery colors: green/amber/red

- [ ] **Step 5: Commit**

```bash
git add simulator/web/src/components/Dashboard.jsx
git commit -m "restyle Dashboard to warm dark palette"
```

---

## Task 3: Restyle Room.jsx — neutral lighting

**Files:**
- Modify: `simulator/web/src/components/Room.jsx`

- [ ] **Step 1: Update color constants and lighting**

Replace the top-level constants:

```jsx
const FLOOR_COLOR = '#2c2c2e';
const WALL_COLOR = '#1c1c1e';
const GRID_COLOR = '#3a3a3c';
```

Update the GridFloor grid helper secondary color from `'#1e1e2a'` to `'#2c2c2e'`.

Update coordinate marker color from `#4a4a5a` to `#3a3a3c`.

- [ ] **Step 2: Update lighting to neutral tones**

Replace the three light sources at the bottom of `Room`:

```jsx
{/* Ambient lighting */}
<ambientLight intensity={0.35} color="#cccccc" />
<directionalLight position={[5, 8, 3]} intensity={0.7} color="#ffffff" castShadow />
<pointLight position={[0, 3, 0]} intensity={0.2} color="#cccccc" />
```

The key change: `ambientLight` color from `#8888aa` (blue-tinted) to `#cccccc` (neutral), and `pointLight` from `#6666aa` (purple) to `#cccccc`.

- [ ] **Step 3: Update monitor emissive color**

In the `Desk` component, change the monitor's emissive from blue to neutral:

```jsx
{/* Monitor */}
<mesh position={[0, 0.72, -0.15]}>
  <boxGeometry args={[0.4, 0.25, 0.02]} />
  <meshStandardMaterial color="#111" emissive="#333333" emissiveIntensity={0.15} />
</mesh>
```

- [ ] **Step 4: Update ceiling light strips**

```jsx
<mesh position={[-2, 2.4, 0]}>
  <boxGeometry args={[0.1, 0.02, 4]} />
  <meshStandardMaterial color="#ddd" emissive="#ffffff" emissiveIntensity={0.2} />
</mesh>
<mesh position={[2, 2.4, 0]}>
  <boxGeometry args={[0.1, 0.02, 4]} />
  <meshStandardMaterial color="#ddd" emissive="#ffffff" emissiveIntensity={0.2} />
</mesh>
```

- [ ] **Step 5: Update furniture accent colors**

Change chair color from `#2a2a40` (blue-tinted) to `#2c2c2e` in both `Desk` and `MeetingTable`.

- [ ] **Step 6: Verify in browser**

Open http://localhost:5173. Confirm:
- Floor and walls are warm grays, no blue tint
- No purple point light visible
- Monitors are dim neutral, not blue-emissive
- Grid lines are warm gray

- [ ] **Step 7: Commit**

```bash
git add simulator/web/src/components/Room.jsx
git commit -m "restyle Room to neutral warm lighting, remove blue tints"
```

---

## Task 4: Restyle PepperModel.jsx — remove blue glow

**Files:**
- Modify: `simulator/web/src/components/PepperModel.jsx`

- [ ] **Step 1: Remove blue emissive from chest tablet**

In the `Torso` component, change the tablet screen material:

```jsx
{/* Chest tablet screen */}
<mesh ref={glowRef} position={[0, 0.22, 0.12]}>
  <boxGeometry args={[0.18, 0.12, 0.015]} />
  <meshStandardMaterial
    color="#1c1c1e"
    emissive="#e5e5e0"
    emissiveIntensity={0.05}
    roughness={0.1}
    metalness={0.5}
  />
</mesh>
```

Change `PEPPER_TABLET` from `'#1a1a2e'` (blue-tinted) to `'#1c1c1e'` at the top.

- [ ] **Step 2: Tone down the breathing animation**

In the `Torso` `useFrame`, update the pulse range to be subtler with neutral emissive:

```jsx
useFrame((state) => {
  if (glowRef.current) {
    const pulse = isSpeaking
      ? 0.15 + Math.sin(state.clock.elapsedTime * 8) * 0.1
      : 0.05 + Math.sin(state.clock.elapsedTime * 1.5) * 0.03;
    glowRef.current.material.emissiveIntensity = pulse;
  }
});
```

- [ ] **Step 3: Update SpeechBubble background**

Change the SpeechBubble plane color from `#1a1a2e` to `#2c2c2e`:

```jsx
<meshBasicMaterial color="#2c2c2e" transparent opacity={0.85} side={THREE.DoubleSide} />
```

- [ ] **Step 4: Verify in browser**

Open http://localhost:5173. Confirm:
- Pepper's chest tablet is dark neutral, not blue
- No blue glow pulses — subtle warm white pulse only
- Overall Pepper model looks clean, white body unchanged

- [ ] **Step 5: Commit**

```bash
git add simulator/web/src/components/PepperModel.jsx
git commit -m "remove blue glow from Pepper model, neutral tablet emissive"
```

---

## Task 5: Add Zustand store fields for chat, search, robot state

**Files:**
- Modify: `simulator/web/src/hooks/usePepperState.js`

- [ ] **Step 1: Add new state fields to the store**

Add these fields to the `create` call, after the existing `uptime: 0`:

```jsx
// Chat
chatMessages: [],
chatLoading: false,

// Search results
searchResults: [],

// Derived robot state
robotState: 'idle', // idle | speaking | thinking | listening
```

- [ ] **Step 2: Add chat action methods**

Add these methods inside the `create` call:

```jsx
addChatMessage: (msg) => set((state) => ({
  chatMessages: [...state.chatMessages, msg],
})),

setChatLoading: (loading) => set({ chatLoading: loading }),

addSearchResult: (result) => set((state) => ({
  searchResults: [...state.searchResults.slice(-2), { ...result, id: Date.now(), dismissAt: Date.now() + 8000 }],
})),

dismissSearchResult: (id) => set((state) => ({
  searchResults: state.searchResults.filter((r) => r.id !== id),
})),
```

- [ ] **Step 3: Update `updateFromWS` to derive robotState and handle search results**

In the `updateFromWS` function, add `robotState` derivation and `searchResults` handling:

```jsx
updateFromWS: (data) => set((state) => {
  let robotState = 'idle';
  if (data.is_speaking) robotState = 'speaking';
  else if (data.current_animation?.includes('Think')) robotState = 'thinking';

  const newSearchResults = data.search_results
    ? [...state.searchResults, ...data.search_results.map((r) => ({ ...r, id: Date.now() + Math.random(), dismissAt: Date.now() + 8000 }))]
    .slice(-3)
    : state.searchResults;

  return {
    connected: true,
    state: data,
    x: data.position?.x ?? 0.5,
    y: data.position?.y ?? 0.5,
    theta: data.position?.theta ?? 0,
    isMoving: data.is_moving ?? false,
    joints: data.joints ?? {},
    battery: data.battery ?? 100,
    posture: data.posture ?? 'StandInit',
    isSpeaking: data.is_speaking ?? false,
    currentSpeech: data.current_speech ?? '',
    speechLanguage: data.speech_language ?? 'en',
    eyeColor: data.eye_color ?? { r: 255, g: 255, b: 255 },
    tabletVisible: data.tablet?.visible ?? false,
    tabletUrl: data.tablet?.url ?? '',
    tabletImage: data.tablet?.image ?? '',
    autonomousLife: data.autonomous_life ?? true,
    faceTracking: data.face_tracking ?? false,
    currentAnimation: data.current_animation,
    hasMap: data.has_map ?? false,
    isExploring: data.is_exploring ?? false,
    navTarget: data.nav_target,
    roomObjects: data.room_objects ?? {},
    apiLog: data.api_log ?? [],
    uptime: data.uptime ?? 0,
    robotState,
    searchResults: newSearchResults,
  };
}),
```

Note: also add `tabletImage` extraction (was missing from original — `data.tablet?.image`).

- [ ] **Step 4: Verify store compiles**

Run: `cd simulator/web && npm run dev`
Check browser console for errors. The store should load without issues.

- [ ] **Step 5: Commit**

```bash
git add simulator/web/src/hooks/usePepperState.js
git commit -m "add chat, search results, and robot state to Zustand store"
```

---

## Task 6: Create ChatPopup.jsx

**Files:**
- Create: `simulator/web/src/components/ChatPopup.jsx`
- Modify: `simulator/web/src/App.jsx` (mount it)

- [ ] **Step 1: Create the ChatPopup component**

Create `simulator/web/src/components/ChatPopup.jsx`:

```jsx
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
```

- [ ] **Step 2: Mount ChatPopup in App.jsx**

Add import at the top of `App.jsx`:

```jsx
import ChatPopup from './components/ChatPopup';
```

Add `<ChatPopup />` inside the viewport div, after `<SpeechOverlay />`:

```jsx
<StatusBar />
<SpeechOverlay />
<ChatPopup />
```

- [ ] **Step 3: Verify in browser**

Open http://localhost:5173. Confirm:
- Chat popup appears bottom-right (offset from dashboard edge)
- Dragging the header moves the popup
- Minimize collapses to pill, close hides completely (C button to reopen)
- Typing a message and pressing Enter sends it (will get connection error since `/chat` endpoint doesn't exist yet — that's OK)
- Color scheme matches warm dark palette

- [ ] **Step 4: Commit**

```bash
git add simulator/web/src/components/ChatPopup.jsx simulator/web/src/App.jsx
git commit -m "add floating draggable ChatPopup component"
```

---

## Task 7: Add POST /chat endpoint to sim_bridge.py

**Files:**
- Modify: `simulator/sim_bridge.py`

- [ ] **Step 1: Add /chat to the POST routes dict**

In `BridgeHandler.do_POST()`, add to the routes dict (after the last entry before the closing `}`):

```python
"/chat":               self._post_chat,
```

- [ ] **Step 2: Implement the _post_chat handler**

Add this method to the `BridgeHandler` class, after `_post_nav_load`:

```python
def _post_chat(self, body):
    text = body.get("text", "")
    if not text:
        return {"success": False, "error": "No text provided"}
    # In sim-only mode, return a mock response
    # When orchestrator is connected, this would forward to it
    print(f"[CHAT] User: {text}")
    mock_responses = [
        "Hello! I'm running in simulator mode right now.",
        "That's an interesting question! Let me think about it.",
        "I'm Pepper, nice to chat with you!",
        "In simulator mode, I can only give mock responses. Connect the orchestrator for real conversation!",
    ]
    import hashlib
    idx = int(hashlib.md5(text.encode()).hexdigest(), 16) % len(mock_responses)
    response_text = mock_responses[idx]
    pepper.say(response_text, "en")
    # Auto-finish speech after delay
    import threading
    def finish():
        import time
        time.sleep(max(1.0, len(response_text.split()) * 0.15))
        pepper.finish_speaking()
    threading.Thread(target=finish, daemon=True).start()
    return {
        "success": True,
        "data": {
            "response": response_text,
            "routed_to": "simulator",
            "tools_used": [],
        }
    }
```

- [ ] **Step 3: Move imports to top level**

The `hashlib` and `threading` imports are already at the top (threading is), but add `hashlib`:

```python
import hashlib
```

Add this to the imports block at the top of the file (after `import threading`).

And remove the inline `import hashlib`, `import threading`, and `import time` from inside `_post_chat`.

- [ ] **Step 4: Test the endpoint**

Run the bridge:
```bash
cd simulator && python sim_bridge.py
```

In another terminal:
```bash
curl -X POST http://localhost:5001/chat -H "Content-Type: application/json" -d '{"text":"hello"}'
```

Expected: `{"success": true, "data": {"response": "...", "routed_to": "simulator", "tools_used": []}}`

- [ ] **Step 5: Test full flow in browser**

With bridge running, open http://localhost:5173. Type "hello" in the chat popup and press Enter. Confirm:
- User message appears as gray bubble
- Pepper's response appears as green bubble
- Pepper's speech overlay shows the response text
- "via simulator" label shown under Pepper's message

- [ ] **Step 6: Commit**

```bash
git add simulator/sim_bridge.py
git commit -m "add POST /chat endpoint to simulator bridge"
```

---

## Task 8: Add search results to sim_state.py + sim_bridge.py

**Files:**
- Modify: `simulator/sim_state.py`
- Modify: `simulator/sim_bridge.py`

- [ ] **Step 1: Add search_results to PepperState**

In `sim_state.py`, add to the `reset()` method (after `self.api_log = []`):

```python
# Search results (for frontend display)
self.search_results = []
```

- [ ] **Step 2: Add push_search_result method**

Add to `PepperState` class (after the `hide_tablet` method):

```python
# ─── Search Results ──────────────────────────────────────────

def push_search_result(self, query, results):
    with self._lock:
        self.search_results.append({
            "query": query,
            "results": results,
            "time": time.strftime("%H:%M:%S"),
        })
        if len(self.search_results) > 5:
            self.search_results.pop(0)

def clear_search_results(self):
    with self._lock:
        self.search_results = []
```

- [ ] **Step 3: Include search_results in to_dict()**

In the `to_dict` method, add after `"api_log"`:

```python
"search_results": self.search_results,
```

Then reset after broadcasting so each result is only sent once:

Actually, a simpler approach: the frontend Zustand store accumulates results. The backend just holds a queue that gets consumed. Add a `pop_search_results` method instead:

```python
def pop_search_results(self):
    with self._lock:
        results = self.search_results[:]
        self.search_results = []
        return results
```

And in `to_dict`, use:
```python
"search_results": self.search_results,
```

Keep it simple — the frontend deduplicates by checking IDs.

- [ ] **Step 4: Add POST /search_results to sim_bridge.py**

Add to the POST routes dict:
```python
"/search_results":     self._post_search_results,
```

Add the handler:
```python
def _post_search_results(self, body):
    query = body.get("query", "")
    results = body.get("results", [])
    pepper.push_search_result(query, results)
    print(f"[SEARCH] query='{query}' results={len(results)}")
    return {"success": True, "data": {"query": query, "count": len(results)}}
```

- [ ] **Step 5: Test the endpoint**

```bash
curl -X POST http://localhost:5001/search_results -H "Content-Type: application/json" -d '{"query":"berlin weather","results":[{"title":"Berlin Weather","snippet":"22°C, partly cloudy","url":"weather.com"}]}'
```

Expected: `{"success": true, "data": {"query": "berlin weather", "count": 1}}`

- [ ] **Step 6: Commit**

```bash
git add simulator/sim_state.py simulator/sim_bridge.py
git commit -m "add search results state and POST /search_results endpoint"
```

---

## Task 9: Create SearchResultPopup.jsx

**Files:**
- Create: `simulator/web/src/components/SearchResultPopup.jsx`
- Modify: `simulator/web/src/App.jsx` (mount it)

- [ ] **Step 1: Create the SearchResultPopup component**

Create `simulator/web/src/components/SearchResultPopup.jsx`:

```jsx
import React, { useEffect } from 'react';
import { usePepperStore } from '../hooks/usePepperState';

function SearchResultCard({ result, onDismiss }) {
  useEffect(() => {
    const remaining = result.dismissAt - Date.now();
    if (remaining <= 0) { onDismiss(); return; }
    const timer = setTimeout(onDismiss, remaining);
    return () => clearTimeout(timer);
  }, [result.dismissAt, onDismiss]);

  const elapsed = Date.now() - (result.dismissAt - 8000);
  const progress = Math.min(1, elapsed / 8000);

  return (
    <div style={{
      width: '320px',
      background: '#2c2c2e',
      border: '1px solid #3a3a3c',
      borderRadius: '10px',
      overflow: 'hidden',
      boxShadow: '0 4px 20px rgba(0,0,0,0.4)',
      fontFamily: "-apple-system, 'Segoe UI', Roboto, sans-serif",
      animation: 'slideInRight 0.3s ease-out',
    }}>
      {/* Header */}
      <div style={{
        padding: '8px 12px',
        borderBottom: '1px solid #3a3a3c',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <span style={{ fontSize: '11px', color: '#999' }}>
          Search: "{result.query}"
        </span>
        <span
          onClick={onDismiss}
          style={{ cursor: 'pointer', color: '#666', fontSize: '12px' }}
        >✕</span>
      </div>

      {/* Results */}
      <div style={{ padding: '10px 12px' }}>
        {(result.results || []).slice(0, 1).map((r, i) => (
          <div key={i}>
            <div style={{ fontSize: '13px', fontWeight: 600, color: '#e5e5e5', marginBottom: '4px' }}>
              {r.title}
            </div>
            <div style={{ fontSize: '12px', color: '#999', lineHeight: '1.4', marginBottom: '4px' }}>
              {r.snippet}
            </div>
            <div style={{ fontSize: '10px', color: '#666' }}>
              {r.url}
            </div>
          </div>
        ))}
      </div>

      {/* Auto-dismiss progress bar */}
      <div style={{ height: '2px', background: '#3a3a3c' }}>
        <div style={{
          height: '100%',
          background: '#8aba8a',
          width: `${(1 - progress) * 100}%`,
          transition: 'width 1s linear',
        }} />
      </div>
    </div>
  );
}

export default function SearchResultPopup() {
  const searchResults = usePepperStore((s) => s.searchResults);
  const dismissSearchResult = usePepperStore((s) => s.dismissSearchResult);

  if (searchResults.length === 0) return null;

  return (
    <div style={{
      position: 'fixed',
      top: '16px',
      right: '400px',
      display: 'flex',
      flexDirection: 'column',
      gap: '8px',
      zIndex: 200,
    }}>
      {searchResults.map((result) => (
        <SearchResultCard
          key={result.id}
          result={result}
          onDismiss={() => dismissSearchResult(result.id)}
        />
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Add CSS animation for slide-in**

Since there's no CSS file, we add a `<style>` tag. In `App.jsx`, add inside the root div (before the Canvas div):

```jsx
<style>{`
  @keyframes slideInRight {
    from { transform: translateX(100px); opacity: 0; }
    to { transform: translateX(0); opacity: 1; }
  }
`}</style>
```

- [ ] **Step 3: Mount SearchResultPopup in App.jsx**

Add import:
```jsx
import SearchResultPopup from './components/SearchResultPopup';
```

Add `<SearchResultPopup />` after `<ChatPopup />` in the viewport div.

- [ ] **Step 4: Test with a manual search result push**

With bridge running:
```bash
curl -X POST http://localhost:5001/search_results -H "Content-Type: application/json" -d '{"query":"berlin weather","results":[{"title":"Berlin Weather Today","snippet":"22°C, partly cloudy. Humidity 65%.","url":"weather.com"}]}'
```

Open http://localhost:5173. Confirm:
- Search result popup appears in top-right (offset from dashboard)
- Shows query, title, snippet, URL
- Auto-dismisses after ~8 seconds
- Close button works

- [ ] **Step 5: Commit**

```bash
git add simulator/web/src/components/SearchResultPopup.jsx simulator/web/src/App.jsx
git commit -m "add SearchResultPopup with auto-dismiss and slide-in animation"
```

---

## Task 10: Add search monitor glow to Room.jsx

**Files:**
- Modify: `simulator/web/src/components/Room.jsx`

- [ ] **Step 1: Import usePepperStore and useFrame**

Add at the top of `Room.jsx`:

```jsx
import { useFrame } from '@react-three/fiber';
import { useRef } from 'react';
```

(React is already imported, `usePepperStore` is already imported.)

- [ ] **Step 2: Add a SearchMonitor component that replaces one desk's monitor**

Convert the first `Desk` component to accept an optional `searchActive` prop, or create a dedicated `SearchMonitor` that wraps a desk's monitor. Simpler approach — add a standalone `SearchMonitor` component:

```jsx
function SearchMonitor({ position }) {
  const monitorRef = useRef();
  const searchResults = usePepperStore((s) => s.searchResults);
  const active = searchResults.length > 0;

  useFrame((state) => {
    if (monitorRef.current) {
      const target = active ? 0.4 : 0.15;
      const current = monitorRef.current.material.emissiveIntensity;
      monitorRef.current.material.emissiveIntensity += (target - current) * 0.05;
    }
  });

  return (
    <mesh ref={monitorRef} position={position}>
      <boxGeometry args={[0.4, 0.25, 0.02]} />
      <meshStandardMaterial
        color="#111"
        emissive={active ? '#e5e5e0' : '#333333'}
        emissiveIntensity={0.15}
      />
    </mesh>
  );
}
```

- [ ] **Step 3: Use SearchMonitor in one Desk**

Modify the first `Desk` (John's desk at `[6.5-4, 0, 1.5-3]`) to use SearchMonitor for its monitor.

Update the `Desk` component to accept an optional `monitorOverride` prop:

```jsx
function Desk({ position, label, monitorOverride }) {
  return (
    <group position={position}>
      {/* Table top */}
      <mesh position={[0, 0.5, 0]}>
        <boxGeometry args={[0.8, 0.03, 0.5]} />
        <meshStandardMaterial color="#3a3020" roughness={0.7} />
      </mesh>
      {/* Legs */}
      {[[-0.35, 0, -0.2], [0.35, 0, -0.2], [-0.35, 0, 0.2], [0.35, 0, 0.2]].map((p, i) => (
        <mesh key={i} position={[p[0], 0.25, p[2]]}>
          <cylinderGeometry args={[0.02, 0.02, 0.5, 8]} />
          <meshStandardMaterial color="#555" />
        </mesh>
      ))}
      {/* Monitor — use override if provided */}
      {monitorOverride || (
        <mesh position={[0, 0.72, -0.15]}>
          <boxGeometry args={[0.4, 0.25, 0.02]} />
          <meshStandardMaterial color="#111" emissive="#333333" emissiveIntensity={0.15} />
        </mesh>
      )}
      {/* Chair */}
      <mesh position={[0, 0.3, 0.4]}>
        <boxGeometry args={[0.3, 0.03, 0.3]} />
        <meshStandardMaterial color="#2c2c2e" />
      </mesh>
    </group>
  );
}
```

Then in the `Room` return, update John's desk:

```jsx
<Desk
  position={[6.5 - 4, 0, 1.5 - 3]}
  label="John"
  monitorOverride={<SearchMonitor position={[0, 0.72, -0.15]} />}
/>
```

- [ ] **Step 4: Verify in browser**

Push a search result via curl, then check that John's desk monitor brightens to warm white. When the search result dismisses, the monitor should dim back down smoothly.

- [ ] **Step 5: Commit**

```bash
git add simulator/web/src/components/Room.jsx
git commit -m "add SearchMonitor glow on desk when search results arrive"
```

---

## Task 11: Create TabletRenderer.js

**Files:**
- Create: `simulator/web/src/components/TabletRenderer.js`

This is a plain JS module (not a React component) that manages an offscreen canvas for the Pepper chest tablet texture.

- [ ] **Step 1: Create the TabletRenderer module**

Create `simulator/web/src/components/TabletRenderer.js`:

```jsx
import * as THREE from 'three';

const CANVAS_W = 256;
const CANVAS_H = 160;

export default class TabletRenderer {
  constructor() {
    this.canvas = document.createElement('canvas');
    this.canvas.width = CANVAS_W;
    this.canvas.height = CANVAS_H;
    this.ctx = this.canvas.getContext('2d');
    this.texture = new THREE.CanvasTexture(this.canvas);
    this.texture.minFilter = THREE.LinearFilter;
    this._animFrame = 0;
  }

  update(robotState, tabletVisible, tabletUrl, tabletImage) {
    this._animFrame++;
    const ctx = this.ctx;

    if (tabletVisible && (tabletUrl || tabletImage)) {
      this._drawContent(ctx, tabletUrl, tabletImage);
    } else {
      this._drawState(ctx, robotState);
    }

    this.texture.needsUpdate = true;
  }

  _drawState(ctx, state) {
    ctx.fillStyle = '#1c1c1e';
    ctx.fillRect(0, 0, CANVAS_W, CANVAS_H);

    switch (state) {
      case 'speaking':
        this._drawWaveform(ctx);
        break;
      case 'thinking':
        this._drawThinking(ctx);
        break;
      case 'listening':
        this._drawListening(ctx);
        break;
      default:
        this._drawIdle(ctx);
    }
  }

  _drawIdle(ctx) {
    const cx = CANVAS_W / 2;
    const cy = CANVAS_H / 2;
    const pulse = 0.4 + Math.sin(this._animFrame * 0.03) * 0.2;
    ctx.beginPath();
    ctx.arc(cx, cy, 12, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(138, 186, 138, ${pulse})`;
    ctx.fill();
    ctx.font = '12px sans-serif';
    ctx.fillStyle = `rgba(153, 153, 153, ${pulse + 0.3})`;
    ctx.textAlign = 'center';
    ctx.fillText('IDLE', cx, cy + 30);
  }

  _drawWaveform(ctx) {
    const cx = CANVAS_W / 2;
    const cy = CANVAS_H / 2;
    const barCount = 8;
    const barWidth = 10;
    const gap = 6;
    const totalWidth = barCount * barWidth + (barCount - 1) * gap;
    const startX = cx - totalWidth / 2;

    for (let i = 0; i < barCount; i++) {
      const phase = this._animFrame * 0.15 + i * 0.8;
      const height = 15 + Math.sin(phase) * 25;
      const x = startX + i * (barWidth + gap);
      const y = cy - height / 2;
      ctx.fillStyle = '#8aba8a';
      ctx.fillRect(x, y, barWidth, height);
    }

    ctx.font = '10px sans-serif';
    ctx.fillStyle = '#666';
    ctx.textAlign = 'center';
    ctx.fillText('SPEAKING', cx, cy + 50);
  }

  _drawThinking(ctx) {
    const cx = CANVAS_W / 2;
    const cy = CANVAS_H / 2;
    const dotCount = 3;
    const gap = 20;
    const startX = cx - (dotCount - 1) * gap / 2;

    for (let i = 0; i < dotCount; i++) {
      const phase = this._animFrame * 0.08 + i * 1.2;
      const radius = 4 + Math.sin(phase) * 2;
      const alpha = 0.4 + Math.sin(phase) * 0.4;
      ctx.beginPath();
      ctx.arc(startX + i * gap, cy, radius, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(229, 229, 229, ${alpha})`;
      ctx.fill();
    }

    ctx.font = '10px sans-serif';
    ctx.fillStyle = '#666';
    ctx.textAlign = 'center';
    ctx.fillText('THINKING', cx, cy + 35);
  }

  _drawListening(ctx) {
    const cx = CANVAS_W / 2;
    const cy = CANVAS_H / 2;
    const ringCount = 3;

    for (let i = 0; i < ringCount; i++) {
      const phase = (this._animFrame * 0.04 + i * 0.5) % 1;
      const radius = 8 + phase * 30;
      const alpha = (1 - phase) * 0.6;
      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(138, 186, 138, ${alpha})`;
      ctx.lineWidth = 2;
      ctx.stroke();
    }

    ctx.beginPath();
    ctx.arc(cx, cy, 6, 0, Math.PI * 2);
    ctx.fillStyle = '#8aba8a';
    ctx.fill();

    ctx.font = '10px sans-serif';
    ctx.fillStyle = '#666';
    ctx.textAlign = 'center';
    ctx.fillText('LISTENING', cx, cy + 40);
  }

  _drawContent(ctx, url, image) {
    ctx.fillStyle = '#1c1c1e';
    ctx.fillRect(0, 0, CANVAS_W, CANVAS_H);

    if (url) {
      ctx.font = 'bold 14px sans-serif';
      ctx.fillStyle = '#e5e5e5';
      ctx.textAlign = 'center';
      ctx.fillText('Web Content', CANVAS_W / 2, 40);

      ctx.font = '10px sans-serif';
      ctx.fillStyle = '#999';
      const displayUrl = url.length > 35 ? url.substring(0, 35) + '...' : url;
      ctx.fillText(displayUrl, CANVAS_W / 2, 60);

      ctx.fillStyle = '#8aba8a';
      ctx.fillRect(CANVAS_W / 2 - 40, 80, 80, 3);
    } else if (image) {
      ctx.font = '12px sans-serif';
      ctx.fillStyle = '#999';
      ctx.textAlign = 'center';
      ctx.fillText('Image', CANVAS_W / 2, CANVAS_H / 2);
    }
  }

  dispose() {
    this.texture.dispose();
  }
}
```

- [ ] **Step 2: Verify the module imports cleanly**

This is a plain class — it will be instantiated in PepperModel. No standalone test needed, but verify no syntax errors by checking the dev server console.

- [ ] **Step 3: Commit**

```bash
git add simulator/web/src/components/TabletRenderer.js
git commit -m "add TabletRenderer: offscreen canvas for chest tablet animations"
```

---

## Task 12: Integrate TabletRenderer into PepperModel.jsx

**Files:**
- Modify: `simulator/web/src/components/PepperModel.jsx`

- [ ] **Step 1: Import TabletRenderer and add store selectors**

Add to imports:

```jsx
import TabletRenderer from './TabletRenderer';
```

In `PepperModel`, add store selectors:

```jsx
const robotState = usePepperStore((s) => s.robotState);
const tabletVisible = usePepperStore((s) => s.tabletVisible);
const tabletUrl = usePepperStore((s) => s.tabletUrl);
const tabletImage = usePepperStore((s) => s.tabletImage);
```

- [ ] **Step 2: Create TabletRenderer instance with useRef + useMemo**

Inside `PepperModel`, add:

```jsx
const tabletRenderer = useMemo(() => new TabletRenderer(), []);
```

And add cleanup:

```jsx
useEffect(() => {
  return () => tabletRenderer.dispose();
}, [tabletRenderer]);
```

(Import `useEffect` at the top — it's not imported yet.)

- [ ] **Step 3: Update the tablet in useFrame**

In the existing `useFrame` callback in `PepperModel`, add after the position updates:

```jsx
tabletRenderer.update(robotState, tabletVisible, tabletUrl, tabletImage);
```

- [ ] **Step 4: Replace Torso's glowRef material with the canvas texture**

In the `Torso` component, we need to pass the texture down. Change `Torso` to accept a `tabletTexture` prop:

```jsx
function Torso({ isSpeaking, tabletTexture }) {
```

Replace the chest tablet screen mesh:

```jsx
{/* Chest tablet screen */}
<mesh position={[0, 0.22, 0.12]}>
  <boxGeometry args={[0.18, 0.12, 0.015]} />
  {tabletTexture ? (
    <meshBasicMaterial map={tabletTexture} />
  ) : (
    <meshStandardMaterial
      color="#1c1c1e"
      emissive="#e5e5e0"
      emissiveIntensity={0.05}
      roughness={0.1}
      metalness={0.5}
    />
  )}
</mesh>
```

Remove the `glowRef` and the `useFrame` inside `Torso` (the breathing animation is now handled by TabletRenderer).

In the `PepperModel` return, pass the texture:

```jsx
<Torso isSpeaking={isSpeaking} tabletTexture={tabletRenderer.texture} />
```

- [ ] **Step 5: Verify in browser**

Open http://localhost:5173. Confirm:
- Pepper's chest tablet shows the "IDLE" animation with pulsing green dot
- When Pepper speaks (trigger via bridge `/speak` endpoint), tablet switches to waveform animation
- No blue glow anywhere on the model

Test speaking:
```bash
curl -X POST http://localhost:5001/speak -H "Content-Type: application/json" -d '{"text":"Hello! I am testing the tablet animation."}'
```

Tablet should show waveform bars while speaking, then return to idle.

Test tablet content:
```bash
curl -X POST http://localhost:5001/tablet/show/url -H "Content-Type: application/json" -d '{"url":"https://weather.com/berlin"}'
```

Tablet should show "Web Content" with the URL.

```bash
curl -X POST http://localhost:5001/tablet/hide
```

Tablet should return to idle animation.

- [ ] **Step 6: Commit**

```bash
git add simulator/web/src/components/PepperModel.jsx
git commit -m "integrate TabletRenderer canvas texture on Pepper chest tablet"
```

---

## Task 13: Final integration test and polish

**Files:**
- All modified files from previous tasks

- [ ] **Step 1: Start the full stack**

```bash
# Terminal 1: Bridge
cd simulator && python sim_bridge.py

# Terminal 2: Frontend
cd simulator/web && npm run dev
```

- [ ] **Step 2: Verify visual restyle (no blue/purple anywhere)**

Open http://localhost:5173. Visually scan the entire page:
- Page background: warm dark gray (#1c1c1e), not black
- Dashboard: #2c2c2e panels with #3a3a3c borders
- StatusBar: warm gray pills, green/red for status, no glow
- SpeechOverlay: warm dark popup, white text
- Room lighting: neutral white/gray, no purple point light
- Floor/walls: warm gray, no blue tint
- Desk monitors: neutral dim, no blue emissive
- Pepper tablet: green idle animation, no blue glow
- Chairs: #2c2c2e, not blue-tinted
- MiniMap: green Pepper dot, not blue
- Fog: warm (#1c1c1e), not blue-black

If any blue/purple is visible, identify the source file and fix.

- [ ] **Step 3: Test chat end-to-end**

1. Open chat popup (should be visible by default)
2. Drag it by header — verify it moves
3. Type "hello" and press Enter — verify user bubble + Pepper response
4. Minimize — verify pill appears
5. Close — verify C button appears, click to reopen
6. Refresh page — verify position and open state persisted

- [ ] **Step 4: Test search results end-to-end**

```bash
curl -X POST http://localhost:5001/search_results -H "Content-Type: application/json" -d '{"query":"berlin weather","results":[{"title":"Berlin Weather Today","snippet":"22°C, partly cloudy. Humidity 65%. Wind 12 km/h NW.","url":"weather.com"}]}'
```

Verify:
- Popup slides in from right, top-right area
- Shows query, title, snippet, URL
- Progress bar shrinks over 8 seconds
- Popup auto-dismisses
- John's desk monitor glows warm during display, dims after

Send 3 rapid results — verify max 3 stack, oldest dismissed.

- [ ] **Step 5: Test tablet animations**

```bash
# Trigger speaking
curl -X POST http://localhost:5001/speak -H "Content-Type: application/json" -d '{"text":"Testing tablet waveform animation display"}'

# Wait 3 seconds, then show URL
curl -X POST http://localhost:5001/tablet/show/url -H "Content-Type: application/json" -d '{"url":"https://example.com/test"}'

# Wait 3 seconds, hide tablet
curl -X POST http://localhost:5001/tablet/hide
```

Verify tablet transitions: idle → waveform (speaking) → content (URL) → idle.

- [ ] **Step 6: Final commit if any fixes were needed**

```bash
git add -A
git commit -m "polish: fix integration issues from final testing"
```

(Skip this step if no fixes were needed.)
