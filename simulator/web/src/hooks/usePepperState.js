import { create } from 'zustand';
import { useEffect, useRef } from 'react';

/**
 * Zustand store for Pepper's state.
 * Updated in real-time via WebSocket from the simulator bridge.
 */
export const usePepperStore = create((set) => ({
  connected: false,
  state: null,

  // Position
  x: 0.5, y: 0.5, theta: 0,
  isMoving: false,

  // Joints
  joints: {},

  // Status
  battery: 100,
  posture: 'StandInit',
  isSpeaking: false,
  currentSpeech: '',
  speechLanguage: 'en',

  // Eyes
  eyeColor: { r: 255, g: 255, b: 255 },

  // Tablet
  tabletVisible: false,
  tabletUrl: '',

  // Awareness
  autonomousLife: true,
  faceTracking: false,

  // Animation
  currentAnimation: null,

  // Navigation
  hasMap: false,
  isExploring: false,
  navTarget: null,
  roomObjects: {},

  // API log
  apiLog: [],

  // Uptime
  uptime: 0,

  // Update from WebSocket message
  updateFromWS: (data) => set({
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
    autonomousLife: data.autonomous_life ?? true,
    faceTracking: data.face_tracking ?? false,
    currentAnimation: data.current_animation,
    hasMap: data.has_map ?? false,
    isExploring: data.is_exploring ?? false,
    navTarget: data.nav_target,
    roomObjects: data.room_objects ?? {},
    apiLog: data.api_log ?? [],
    uptime: data.uptime ?? 0,
  }),

  setDisconnected: () => set({ connected: false }),
}));


/**
 * Hook to maintain WebSocket connection to the simulator bridge.
 * Automatically reconnects on disconnect.
 */
export function usePepperWebSocket(url = 'ws://localhost:5003') {
  const wsRef = useRef(null);
  const reconnectRef = useRef(null);
  const updateFromWS = usePepperStore((s) => s.updateFromWS);
  const setDisconnected = usePepperStore((s) => s.setDisconnected);

  useEffect(() => {
    function connect() {
      if (wsRef.current?.readyState === WebSocket.OPEN) return;

      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('[WS] Connected to simulator');
        if (reconnectRef.current) {
          clearInterval(reconnectRef.current);
          reconnectRef.current = null;
        }
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          updateFromWS(data);
        } catch (e) {
          // ignore parse errors
        }
      };

      ws.onclose = () => {
        setDisconnected();
        console.log('[WS] Disconnected. Reconnecting...');
        if (!reconnectRef.current) {
          reconnectRef.current = setInterval(() => connect(), 2000);
        }
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    connect();

    return () => {
      if (reconnectRef.current) clearInterval(reconnectRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [url, updateFromWS, setDisconnected]);
}
