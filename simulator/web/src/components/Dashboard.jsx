import React from 'react';
import { usePepperStore } from '../hooks/usePepperState';

/**
 * Dashboard panel showing:
 * - Connection status
 * - Battery level
 * - Position/orientation
 * - Joint angles
 * - Current speech
 * - API call log
 */

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

function MiniMap() {
  const x = usePepperStore((s) => s.x);
  const y = usePepperStore((s) => s.y);
  const theta = usePepperStore((s) => s.theta);
  const roomObjects = usePepperStore((s) => s.roomObjects);

  const mapW = 340;
  const mapH = 80;
  const scaleX = mapW / 8;
  const scaleY = mapH / 6;

  return (
    <div style={styles.miniMap}>
      <svg width={mapW} height={mapH} viewBox={`0 0 ${mapW} ${mapH}`}>
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
      </svg>
    </div>
  );
}

export default function Dashboard() {
  const connected = usePepperStore((s) => s.connected);
  const battery = usePepperStore((s) => s.battery);
  const x = usePepperStore((s) => s.x);
  const y = usePepperStore((s) => s.y);
  const theta = usePepperStore((s) => s.theta);
  const posture = usePepperStore((s) => s.posture);
  const isSpeaking = usePepperStore((s) => s.isSpeaking);
  const currentSpeech = usePepperStore((s) => s.currentSpeech);
  const speechLanguage = usePepperStore((s) => s.speechLanguage);
  const isMoving = usePepperStore((s) => s.isMoving);
  const eyeColor = usePepperStore((s) => s.eyeColor);
  const autonomousLife = usePepperStore((s) => s.autonomousLife);
  const faceTracking = usePepperStore((s) => s.faceTracking);
  const currentAnimation = usePepperStore((s) => s.currentAnimation);
  const uptime = usePepperStore((s) => s.uptime);
  const apiLog = usePepperStore((s) => s.apiLog);
  const joints = usePepperStore((s) => s.joints);

  const formatTime = (s) => {
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    return `${h}h ${m}m`;
  };

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <div style={styles.statusDot(connected)} />
        <div style={styles.title}>Pepper Simulator</div>
        <div style={{ marginLeft: 'auto', fontSize: '10px', color: '#666' }}>
          {connected ? 'LIVE' : 'OFFLINE'}
        </div>
      </div>

      {/* Status */}
      <div style={styles.section}>
        <div style={styles.sectionTitle}>Status</div>
        <div style={styles.row}>
          <span style={styles.label}>Battery</span>
          <span style={styles.battery(battery)}>{battery}%</span>
        </div>
        <div style={styles.row}>
          <span style={styles.label}>Posture</span>
          <span style={styles.value}>{posture}</span>
        </div>
        <div style={styles.row}>
          <span style={styles.label}>Uptime</span>
          <span style={styles.value}>{formatTime(uptime)}</span>
        </div>
        <div style={styles.row}>
          <span style={styles.label}>Moving</span>
          <span style={{ color: isMoving ? '#8aba8a' : '#666' }}>
            {isMoving ? 'YES' : 'no'}
          </span>
        </div>
        <div style={styles.row}>
          <span style={styles.label}>Eyes</span>
          <span style={{ color: `rgb(${eyeColor.r},${eyeColor.g},${eyeColor.b})` }}>
            ● rgb({eyeColor.r},{eyeColor.g},{eyeColor.b})
          </span>
        </div>
        <div style={styles.row}>
          <span style={styles.label}>Auto Life</span>
          <span style={styles.value}>{autonomousLife ? 'on' : 'off'}</span>
        </div>
        {currentAnimation && (
          <div style={styles.row}>
            <span style={styles.label}>Animation</span>
            <span style={{ color: '#d4a847' }}>{currentAnimation.split('/').pop()}</span>
          </div>
        )}
      </div>

      {/* Position */}
      <div style={styles.section}>
        <div style={styles.sectionTitle}>Position</div>
        <div style={styles.posIndicator}>
          <span>x: <span style={styles.value}>{x.toFixed(2)}m</span></span>
          <span>y: <span style={styles.value}>{y.toFixed(2)}m</span></span>
          <span>θ: <span style={styles.value}>{(theta * 180 / Math.PI).toFixed(1)}°</span></span>
        </div>
        <MiniMap />
      </div>

      {/* Speech */}
      <div style={styles.section}>
        <div style={styles.sectionTitle}>
          Speech {isSpeaking && <span style={{ color: '#8aba8a' }}>● speaking ({speechLanguage})</span>}
        </div>
        <div style={styles.speechBox}>
          {currentSpeech || '(silent)'}
        </div>
      </div>

      {/* Key Joints */}
      <div style={styles.section}>
        <div style={styles.sectionTitle}>Key Joints (rad)</div>
        {['HeadYaw', 'HeadPitch', 'LShoulderPitch', 'RShoulderPitch'].map((j) => (
          <div key={j} style={styles.row}>
            <span style={styles.label}>{j}</span>
            <span style={styles.value}>{(joints[j] ?? 0).toFixed(3)}</span>
          </div>
        ))}
      </div>

      {/* API Log */}
      <div style={{ ...styles.section, padding: '12px 20px 4px' }}>
        <div style={styles.sectionTitle}>API Log</div>
      </div>
      <div style={styles.logContainer}>
        {[...apiLog].reverse().map((entry, i) => (
          <div key={i} style={styles.logEntry}>
            <span style={styles.logTime}>{entry.time}</span>
            <span style={styles.logMethod(entry.method)}>{entry.method}</span>
            <span style={styles.logEndpoint}>{entry.endpoint}</span>
          </div>
        ))}
        {apiLog.length === 0 && (
          <div style={{ color: '#3a3a3c', fontStyle: 'italic' }}>
            Waiting for API calls...
          </div>
        )}
      </div>
    </div>
  );
}
