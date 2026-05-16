import React, { Suspense } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Html, Environment } from '@react-three/drei';
import PepperModel from './components/PepperModel';
import Room from './components/Room';
import Dashboard from './components/Dashboard';
import { usePepperWebSocket, usePepperStore } from './hooks/usePepperState';

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
      background: 'rgba(10, 10, 20, 0.9)',
      border: '1px solid rgba(68, 136, 255, 0.3)',
      borderRadius: '12px',
      fontFamily: "'Space Grotesk', sans-serif",
      fontSize: '15px',
      color: '#c0d0ff',
      textAlign: 'center',
      backdropFilter: 'blur(10px)',
      zIndex: 100,
      pointerEvents: 'none',
    }}>
      <div style={{
        fontSize: '9px',
        color: '#4488ff',
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
        background: 'rgba(10, 10, 20, 0.85)',
        border: `1px solid ${connected ? '#1a3a2a' : '#3a1a1a'}`,
        borderRadius: '6px',
        color: connected ? '#44ff88' : '#ff4444',
        backdropFilter: 'blur(8px)',
      }}>
        {connected ? '● CONNECTED' : '○ DISCONNECTED'}
      </div>

      <div style={{
        padding: '6px 12px',
        background: 'rgba(10, 10, 20, 0.85)',
        border: '1px solid #1a1a2e',
        borderRadius: '6px',
        color: battery > 50 ? '#44ff88' : battery > 20 ? '#ffaa44' : '#ff4444',
        backdropFilter: 'blur(8px)',
      }}>
        🔋 {battery}%
      </div>

      <div style={{
        padding: '6px 12px',
        background: 'rgba(10, 10, 20, 0.85)',
        border: '1px solid #1a1a2e',
        borderRadius: '6px',
        color: '#a0a0c0',
        backdropFilter: 'blur(8px)',
      }}>
        {posture} {isMoving ? '→' : ''}
      </div>
    </div>
  );
}

function LoadingFallback() {
  return (
    <Html center>
      <div style={{
        fontFamily: "'Space Grotesk', sans-serif",
        color: '#4488ff',
        fontSize: '18px',
      }}>
        Loading Simulator...
      </div>
    </Html>
  );
}

export default function App() {
  // Connect to WebSocket
  usePepperWebSocket('ws://localhost:5003');

  return (
    <div style={{ display: 'flex', width: '100vw', height: '100vh', background: '#0a0a0f' }}>
      {/* 3D Viewport */}
      <div style={{ flex: 1, position: 'relative' }}>
        <Canvas
          camera={{ position: [3, 4, 6], fov: 50, near: 0.1, far: 100 }}
          shadows
          gl={{ antialias: true }}
          style={{ background: '#0a0a0f' }}
        >
          <Suspense fallback={<LoadingFallback />}>
            <Room />
            <PepperModel />
          </Suspense>

          <OrbitControls
            enableDamping
            dampingFactor={0.05}
            maxPolarAngle={Math.PI / 2.1}
            minDistance={2}
            maxDistance={15}
            target={[0, 0.5, 0]}
          />

          {/* Fog for atmosphere */}
          <fog attach="fog" args={['#0a0a0f', 8, 20]} />
        </Canvas>

        <StatusBar />
        <SpeechOverlay />

        {/* Title watermark */}
        <div style={{
          position: 'absolute',
          bottom: '16px',
          left: '16px',
          fontFamily: "'Space Grotesk', sans-serif",
          fontSize: '11px',
          color: '#2a2a3a',
          zIndex: 100,
          pointerEvents: 'none',
        }}>
          PEPPER AI × SIMULATOR v1.0
        </div>
      </div>

      {/* Dashboard */}
      <Dashboard />
    </div>
  );
}
