import React, { Suspense } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Html, Environment } from '@react-three/drei';
import PepperModel from './components/PepperModel';
import Room from './components/Room';
import Dashboard from './components/Dashboard';
import ChatPopup from './components/ChatPopup';
import SearchResultPopup from './components/SearchResultPopup';
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
      fontFamily: "-apple-system, 'Segoe UI', Roboto, sans-serif",
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

export default function App() {
  usePepperWebSocket('ws://localhost:5003');

  return (
    <div style={{ display: 'flex', width: '100vw', height: '100vh', background: '#1c1c1e' }}>
      <style>{`
        @keyframes slideInRight {
          from { transform: translateX(100px); opacity: 0; }
          to { transform: translateX(0); opacity: 1; }
        }
        @keyframes shrinkWidth {
          from { width: 100%; }
          to { width: 0%; }
        }
      `}</style>
      {/* 3D Viewport */}
      <div style={{ flex: 1, position: 'relative' }}>
        <Canvas
          camera={{ position: [3, 4, 6], fov: 50, near: 0.1, far: 100 }}
          shadows
          gl={{ antialias: true }}
          style={{ background: '#1c1c1e' }}
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
          <fog attach="fog" args={['#1c1c1e', 8, 20]} />
        </Canvas>

        <StatusBar />
        <SpeechOverlay />
        <ChatPopup />
        <SearchResultPopup />

        {/* Title watermark */}
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
      </div>

      {/* Dashboard */}
      <Dashboard />
    </div>
  );
}
