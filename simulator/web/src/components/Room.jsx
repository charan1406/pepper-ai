import React, { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import { usePepperStore } from '../hooks/usePepperState';
import * as THREE from 'three';

/**
 * 3D Room environment — lab setting with furniture objects.
 * Objects match the simulated room layout from PepperState.
 */

const FLOOR_COLOR = '#2c2c2e';
const WALL_COLOR = '#1c1c1e';
const GRID_COLOR = '#3a3a3c';

function GridFloor() {
  return (
    <group>
      {/* Main floor */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.25, 0]}>
        <planeGeometry args={[8, 6]} />
        <meshStandardMaterial color={FLOOR_COLOR} roughness={0.8} />
      </mesh>

      {/* Grid overlay */}
      <gridHelper
        args={[8, 16, GRID_COLOR, '#2c2c2e']}
        position={[0, -0.249, 0]}
      />

      {/* Coordinate markers */}
      {[0, 1, 2, 3].map((i) => (
        <mesh key={`xm-${i}`} position={[i - 4 + 0.5, -0.248, -3]} rotation={[-Math.PI/2, 0, 0]}>
          <circleGeometry args={[0.03, 8]} />
          <meshBasicMaterial color="#3a3a3c" />
        </mesh>
      ))}
    </group>
  );
}

function Wall({ position, rotation, width, height = 2.5 }) {
  return (
    <mesh position={position} rotation={rotation}>
      <planeGeometry args={[width, height]} />
      <meshStandardMaterial
        color={WALL_COLOR}
        roughness={0.9}
        transparent
        opacity={0.3}
        side={THREE.DoubleSide}
      />
    </mesh>
  );
}

function SearchMonitor({ position }) {
  const monitorRef = useRef();
  const searchResults = usePepperStore((s) => s.searchResults);
  const active = searchResults.length > 0;

  useFrame(() => {
    if (monitorRef.current) {
      const target = active ? 0.4 : 0.15;
      const current = monitorRef.current.material.emissiveIntensity;
      monitorRef.current.material.emissiveIntensity += (target - current) * 0.05;
      monitorRef.current.material.emissive.set(active ? '#e5e5e0' : '#333333');
    }
  });

  return (
    <mesh ref={monitorRef} position={position}>
      <boxGeometry args={[0.4, 0.25, 0.02]} />
      <meshStandardMaterial color="#111" emissive="#333333" emissiveIntensity={0.15} />
    </mesh>
  );
}

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

function CoffeeMachine({ position }) {
  return (
    <group position={position}>
      <mesh position={[0, 0.3, 0]}>
        <boxGeometry args={[0.3, 0.6, 0.25]} />
        <meshStandardMaterial color="#333" roughness={0.5} metalness={0.3} />
      </mesh>
      {/* Red light */}
      <mesh position={[0.05, 0.5, 0.13]}>
        <sphereGeometry args={[0.015, 8, 8]} />
        <meshStandardMaterial color="#ff3333" emissive="#ff3333" emissiveIntensity={0.5} />
      </mesh>
    </group>
  );
}

function Whiteboard({ position }) {
  return (
    <group position={position}>
      <mesh position={[0, 1.0, 0]}>
        <boxGeometry args={[1.5, 1.0, 0.03]} />
        <meshStandardMaterial color="#eeeedd" roughness={0.3} />
      </mesh>
      {/* Frame */}
      <mesh position={[0, 1.0, -0.02]}>
        <boxGeometry args={[1.55, 1.05, 0.02]} />
        <meshStandardMaterial color="#666" metalness={0.4} />
      </mesh>
    </group>
  );
}

function MeetingTable({ position }) {
  return (
    <group position={position}>
      <mesh position={[0, 0.5, 0]}>
        <cylinderGeometry args={[0.6, 0.6, 0.04, 24]} />
        <meshStandardMaterial color="#3a3020" roughness={0.6} />
      </mesh>
      <mesh position={[0, 0.25, 0]}>
        <cylinderGeometry args={[0.05, 0.15, 0.5, 12]} />
        <meshStandardMaterial color="#555" metalness={0.3} />
      </mesh>
      {/* Chairs around the table */}
      {[0, 1.57, 3.14, 4.71].map((angle, i) => (
        <mesh key={i} position={[Math.cos(angle) * 0.9, 0.25, Math.sin(angle) * 0.9]}>
          <boxGeometry args={[0.25, 0.03, 0.25]} />
          <meshStandardMaterial color="#2c2c2e" />
        </mesh>
      ))}
    </group>
  );
}

function FanucArm({ position }) {
  return (
    <group position={position}>
      {/* Base */}
      <mesh position={[0, 0.15, 0]}>
        <cylinderGeometry args={[0.2, 0.25, 0.3, 16]} />
        <meshStandardMaterial color="#44aa33" roughness={0.5} metalness={0.2} />
      </mesh>
      {/* Arm segment 1 */}
      <mesh position={[0, 0.55, 0]}>
        <boxGeometry args={[0.1, 0.5, 0.1]} />
        <meshStandardMaterial color="#44aa33" roughness={0.5} metalness={0.2} />
      </mesh>
      {/* Arm segment 2 */}
      <mesh position={[0.15, 0.8, 0]} rotation={[0, 0, 0.5]}>
        <boxGeometry args={[0.08, 0.4, 0.08]} />
        <meshStandardMaterial color="#338822" roughness={0.5} metalness={0.2} />
      </mesh>
    </group>
  );
}

function ChargingStation({ position }) {
  return (
    <group position={position}>
      <mesh position={[0, 0.05, 0]}>
        <boxGeometry args={[0.4, 0.1, 0.3]} />
        <meshStandardMaterial color="#222" />
      </mesh>
      {/* Green indicator */}
      <mesh position={[0, 0.12, 0.14]}>
        <sphereGeometry args={[0.02, 8, 8]} />
        <meshStandardMaterial color="#33ff33" emissive="#33ff33" emissiveIntensity={0.5} />
      </mesh>
    </group>
  );
}

function DoorFrame({ position }) {
  return (
    <group position={position}>
      {/* Left post */}
      <mesh position={[-0.5, 1.0, 0]}>
        <boxGeometry args={[0.08, 2.0, 0.1]} />
        <meshStandardMaterial color="#555" />
      </mesh>
      {/* Right post */}
      <mesh position={[0.5, 1.0, 0]}>
        <boxGeometry args={[0.08, 2.0, 0.1]} />
        <meshStandardMaterial color="#555" />
      </mesh>
      {/* Top */}
      <mesh position={[0, 2.0, 0]}>
        <boxGeometry args={[1.08, 0.08, 0.1]} />
        <meshStandardMaterial color="#555" />
      </mesh>
    </group>
  );
}

export default function Room() {
  // Room is 8m x 6m, centered at origin → (-4,-3) to (4,3)
  return (
    <group>
      <GridFloor />

      {/* Walls (transparent, gives sense of boundary) */}
      <Wall position={[0, 1, -3]} rotation={[0, 0, 0]} width={8} />
      <Wall position={[0, 1, 3]} rotation={[0, Math.PI, 0]} width={8} />
      <Wall position={[-4, 1, 0]} rotation={[0, Math.PI / 2, 0]} width={6} />
      <Wall position={[4, 1, 0]} rotation={[0, -Math.PI / 2, 0]} width={6} />

      {/* Room objects — positions converted from sim coords to 3D scene */}
      {/* sim(x,y) → scene(x-4, 0, y-3) */}

      <DoorFrame position={[0 - 4, 0, 0 - 3]} />
      <ChargingStation position={[0.5 - 4, 0, 0.5 - 3]} />
      <CoffeeMachine position={[0.5 - 4, 0, 5.0 - 3]} />
      <Whiteboard position={[4.0 - 4, 0, 5.5 - 3]} />
      <MeetingTable position={[3.0 - 4, 0, 3.0 - 3]} />
      <Desk position={[6.5 - 4, 0, 1.5 - 3]} label="John" monitorOverride={<SearchMonitor position={[0, 0.72, -0.15]} />} />
      <Desk position={[1.0 - 4, 0, 3.0 - 3]} label="Priya" />
      <Desk position={[6.5 - 4, 0, 4.0 - 3]} label="Desk 3" />
      <FanucArm position={[7.0 - 4, 0, 0.5 - 3]} />

      {/* Ambient lighting */}
      <ambientLight intensity={0.35} color="#cccccc" />
      <directionalLight position={[5, 8, 3]} intensity={0.7} color="#ffffff" castShadow />
      <pointLight position={[0, 3, 0]} intensity={0.2} color="#cccccc" />

      {/* Ceiling light strips */}
      <mesh position={[-2, 2.4, 0]}>
        <boxGeometry args={[0.1, 0.02, 4]} />
        <meshStandardMaterial color="#ddd" emissive="#ffffff" emissiveIntensity={0.2} />
      </mesh>
      <mesh position={[2, 2.4, 0]}>
        <boxGeometry args={[0.1, 0.02, 4]} />
        <meshStandardMaterial color="#ddd" emissive="#ffffff" emissiveIntensity={0.2} />
      </mesh>
    </group>
  );
}
