# 3D Simulator Enhancements — Design Spec

**Date**: 2026-05-18
**Status**: Approved
**Scope**: Visual restyle + chat popup + tablet animations + search results display

---

## 1. Visual Overhaul: Warm Dark (macOS Aesthetic)

The entire simulator frontend is restyled from the current blue/purple glow theme to a warm macOS dark mode palette.

### Color Palette

| Token | Value | Usage |
|---|---|---|
| `--bg-deep` | `#1c1c1e` | Page background, input fields, 3D canvas surround |
| `--bg-panel` | `#2c2c2e` | Panels, cards, popups, dashboard |
| `--bg-elevated` | `#3a3a3c` | Hover states, message bubbles (user), dividers |
| `--border` | `#3a3a3c` | All borders — 1px solid, no colored borders (same as elevated, intentional) |
| `--text-primary` | `#e5e5e5` | Headings, labels, primary content |
| `--text-secondary` | `#999999` | Values, metadata, timestamps |
| `--text-muted` | `#666666` | Placeholders, disabled, subtle labels |
| `--accent-positive` | `#8aba8a` | Online, battery OK, success, Pepper responses |
| `--accent-negative` | `#ba8a8a` | Errors, warnings, low battery |
| `--accent-neutral` | `#a0a0a0` | Neutral indicators |

### Rules

- Zero glow effects. No `box-shadow` with color, no `text-shadow`, no bloom.
- Shadows allowed only as `rgba(0,0,0,0.2–0.4)` for depth.
- No blue or purple anywhere in the UI.
- Borders: `1px solid var(--border)`, never thicker.
- Border radius: `10px` for popups/cards, `6px` for inputs/buttons, `4px` for small elements.
- Font: system stack (`-apple-system, 'Segoe UI', Roboto, sans-serif`).
- 3D scene: neutral ambient light, no colored fog or post-processing bloom.

### Files Affected

- `simulator/web/src/App.jsx` — root layout, background color
- `simulator/web/src/App.css` — all global styles
- `simulator/web/src/components/Dashboard.jsx` — panel backgrounds, text colors, borders
- `simulator/web/src/components/Room.jsx` — scene lighting, material colors
- `simulator/web/src/components/PepperModel.jsx` — LED eye color defaults, tablet glow removal
- `simulator/web/src/components/StatusBar.jsx` (if exists) — restyle
- `simulator/web/src/components/SpeechOverlay.jsx` (if exists) — restyle

---

## 2. Chat Popup (Floating, Draggable, Minimizable)

A floating chat panel overlaying the 3D viewport for direct conversation with Pepper.

### Behavior

- **Default position**: Bottom-right of the viewport, offset 16px from edges.
- **Draggable**: Click-and-drag on the header bar to reposition anywhere within the viewport.
- **Minimizable**: Collapses to a small pill/icon (shows "Chat" + unread count). Click to expand.
- **Closable**: Close button hides completely; a floating action button re-opens it.
- **Persistence**: Position (x, y) and open/closed state saved to `localStorage`, restored on page load.
- **Resizable**: No. Fixed width ~300px, height ~400px (or smaller on mobile).

### Message Flow

1. User types message in input field, presses Enter or send button.
2. Frontend sends `POST http://localhost:5001/chat` with `{"text": "user message"}`.
3. `sim_bridge.py` receives the request, forwards to the orchestrator pipeline.
4. Orchestrator processes (reflex → fast → deep routing), returns response.
5. Bridge returns `{"response": "Pepper's spoken text", "action": "...", ...}`.
6. Frontend appends Pepper's response as a new message bubble.
7. If Pepper is speaking (via WebSocket `speech` state), show a typing indicator before the response arrives.

### New Bridge Endpoint

```
POST /chat
Body: {"text": "string"}
Response: {"response": "string", "routed_to": "reflex|fast|deep", "tools_used": [...]}
```

Added to `simulator/sim_bridge.py`. In sim-only mode (no orchestrator running), returns a mock response indicating the orchestrator is offline.

### UI Structure

```
ChatPopup (floating div, position: fixed)
├── Header (draggable handle)
│   ├── "Chat" label
│   └── Minimize button, Close button
├── Messages area (scrollable)
│   ├── UserMessage (bg: --bg-elevated, text: --text-primary)
│   ├── PepperMessage (bg: #2a3a2a, text: --accent-positive)
│   └── TypingIndicator (three dots animation)
└── Input bar
    ├── Text input (bg: --bg-deep, border: --border)
    └── Send button
```

### Styling

- Background: `var(--bg-panel)`
- Border: `1px solid var(--border)`
- Border-radius: `10px`
- Shadow: `0 4px 20px rgba(0,0,0,0.4)`
- User messages: `var(--bg-elevated)` background
- Pepper messages: `#2a3a2a` background with `var(--accent-positive)` text
- No colored borders, no glow on focus

### New File

- `simulator/web/src/components/ChatPopup.jsx` — self-contained component with drag logic, message state, API calls

---

## 3. Pepper's Chest Tablet (Animated States + Content)

The chest tablet on the 3D Pepper model shows animated state indicators by default and switches to real content when triggered via the bridge API.

### Default State Animations

| Robot State | Tablet Animation |
|---|---|
| Idle | Subtle breathing pulse (opacity oscillation on a neutral icon) |
| Speaking | Vertical audio waveform bars (6–8 bars, heights animate) |
| Thinking | Pulsing dot or spinner |
| Listening | Concentric ripple rings |

State is derived from the existing WebSocket fields: `speech.is_speaking`, `speech.text`, and a new `robot_state` field (or inferred from current state).

### Content Mode

When the bridge receives `POST /tablet/show/url` or `POST /tablet/show/image`:
1. WebSocket broadcasts `tablet: {visible: true, url: "...", image: "..."}`.
2. Frontend switches the tablet texture from animated state to content rendering.
3. Content rendered on an offscreen `<canvas>` element (HTML-to-canvas for URLs, direct draw for images).
4. Canvas converted to `THREE.CanvasTexture` and applied to the tablet mesh material.

When `POST /tablet/hide` is called, tablet returns to animated state mode.

### Implementation Approach

- Offscreen `<canvas>` (256x160 or similar aspect ratio matching Pepper's 10.1" 1280x800 tablet).
- For URL content: render a simplified card (title, snippet, favicon) — not a full web render.
- For image content: draw the image scaled to fit the canvas.
- `requestAnimationFrame` loop updates the canvas texture each frame (for animations) or on content change.
- The `PepperModel.jsx` chest tablet mesh gets its `material.map` set to this `CanvasTexture`.

### State

Existing Zustand store fields are sufficient:
- `tablet.visible` — `true` when showing content, `false` for animated state mode
- `tablet.url` — URL to display
- `tablet.image` — image data/URL to display

New field needed:
- `robotState` — enum: `idle | speaking | thinking | listening` (derived from existing WebSocket data)

### Files Affected

- `simulator/web/src/components/PepperModel.jsx` — tablet mesh material, canvas texture logic
- `simulator/web/src/hooks/usePepperState.js` — add `robotState` derivation

### New File

- `simulator/web/src/components/TabletRenderer.js` — offscreen canvas logic, animation loops, content rendering (used by PepperModel)

---

## 4. Web Search Results (Monitor Glow + Floating Popup)

When Pepper performs a web search, results are shown both in the 3D scene and as a readable overlay.

### 3D Scene: Monitor Glow

- One of the existing desk monitors in `Room.jsx` is designated as the "search monitor".
- When search results arrive, the monitor's emissive material intensity increases (warm white `#e5e5e0`, not blue).
- Glow fades out over 3 seconds when the floating popup dismisses.
- No bloom post-processing — just emissive material change.

### Floating Results Popup

- Appears in the top-right area of the viewport (does not overlap with chat popup in bottom-right).
- Shows: search query, top result title, snippet (2–3 lines), source domain.
- Auto-dismisses after 8 seconds.
- Manual close button (x).
- Slides in from the right, fades out on dismiss.
- Stacks if multiple searches happen in quick succession (max 3 visible, oldest dismissed).

### Data Flow

1. Orchestrator's deep brain calls the `web_search` tool.
2. Search results are broadcast via WebSocket as a new event: `search_results: {query, results: [{title, snippet, url}]}`.
3. Frontend Zustand store picks up the event, adds to a search results queue.
4. `SearchResultsPopup` component renders from the queue.
5. Monitor glow triggered simultaneously via the same store update.

### New WebSocket Event

```json
{
  "type": "search_results",
  "data": {
    "query": "berlin weather",
    "results": [
      {"title": "Berlin Weather Today", "snippet": "22°C, partly cloudy...", "url": "weather.com"}
    ]
  }
}
```

Added to `sim_state.py` WebSocket broadcast. The orchestrator (or a hook in the tool execution) triggers this.

### UI Structure

```
SearchResultPopup (floating div, position: fixed, top-right)
├── Header
│   ├── Search icon + query text
│   └── Close button
├── Result card
│   ├── Title (--text-primary, font-weight 600)
│   ├── Snippet (--text-secondary, 2-3 lines)
│   └── Source domain (--text-muted)
└── Auto-dismiss progress bar (thin line at bottom)
```

### Styling

- Background: `var(--bg-panel)`
- Border: `1px solid var(--border)`
- Border-radius: `10px`
- Shadow: `0 4px 20px rgba(0,0,0,0.4)`
- Width: ~320px
- Entrance: slide in from right (CSS transform)
- Exit: fade out (CSS opacity)

### Files Affected

- `simulator/web/src/components/Room.jsx` — search monitor emissive material
- `simulator/web/src/hooks/usePepperState.js` — search results state + WebSocket handler
- `simulator/sim_state.py` — broadcast search results event
- `simulator/sim_bridge.py` — accept search result notifications (or hook into orchestrator)

### New Files

- `simulator/web/src/components/SearchResultPopup.jsx` — floating results overlay

---

## 5. Summary of New Files

| File | Purpose |
|---|---|
| `simulator/web/src/components/ChatPopup.jsx` | Floating draggable chat panel |
| `simulator/web/src/components/TabletRenderer.js` | Offscreen canvas for tablet texture |
| `simulator/web/src/components/SearchResultPopup.jsx` | Floating search results overlay |

## 6. Summary of Modified Files

| File | Changes |
|---|---|
| `simulator/web/src/App.jsx` | Mount ChatPopup + SearchResultPopup, restyle layout |
| `simulator/web/src/App.css` | Full restyle to warm dark palette, CSS custom properties |
| `simulator/web/src/components/Dashboard.jsx` | Restyle all panels to warm dark |
| `simulator/web/src/components/Room.jsx` | Neutral scene lighting, search monitor emissive |
| `simulator/web/src/components/PepperModel.jsx` | Tablet canvas texture, remove glow |
| `simulator/web/src/components/SpeechOverlay.jsx` | Restyle to warm dark |
| `simulator/web/src/components/StatusBar.jsx` | Restyle to warm dark |
| `simulator/web/src/hooks/usePepperState.js` | Add robotState, searchResults, chat state |
| `simulator/sim_bridge.py` | Add POST /chat endpoint |
| `simulator/sim_state.py` | Broadcast search_results event, robotState derivation |

## 7. Dependencies

No new npm packages required. All functionality uses:
- React state + refs (drag logic)
- Canvas 2D API (tablet rendering)
- THREE.CanvasTexture (existing Three.js)
- CSS transitions/animations (popups)
- fetch API (chat endpoint)
