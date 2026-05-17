import React, { useRef, useMemo, useEffect } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { usePepperStore } from '../hooks/usePepperState';
import TabletRenderer from './TabletRenderer';

/**
 * Stylized low-poly Pepper robot model.
 * All joints are articulated and driven by the simulator state.
 * Design: clean white body, rounded forms, glowing LED eyes,
 * chest tablet as a dark screen, smooth arm movement.
 */

const PEPPER_WHITE = '#f0f0f0';
const PEPPER_LIGHT = '#e8e8e8';
const PEPPER_DARK = '#d0d0d0';
const PEPPER_TABLET = '#1c1c1e';

function EyeLED({ position, color }) {
  return (
    <mesh position={position}>
      <sphereGeometry args={[0.022, 16, 16]} />
      <meshStandardMaterial
        color={`rgb(${color.r},${color.g},${color.b})`}
        emissive={`rgb(${color.r},${color.g},${color.b})`}
        emissiveIntensity={0.8}
      />
    </mesh>
  );
}

function Head({ headYaw, headPitch, eyeColor }) {
  const headRef = useRef();

  useFrame(() => {
    if (headRef.current) {
      headRef.current.rotation.y = headYaw;
      headRef.current.rotation.x = headPitch;
    }
  });

  return (
    <group ref={headRef} position={[0, 0.52, 0]}>
      {/* Main head sphere */}
      <mesh position={[0, 0.1, 0]}>
        <sphereGeometry args={[0.12, 24, 24]} />
        <meshStandardMaterial color={PEPPER_WHITE} roughness={0.3} metalness={0.1} />
      </mesh>

      {/* Forehead bump (characteristic Pepper shape) */}
      <mesh position={[0, 0.18, 0.03]}>
        <sphereGeometry args={[0.08, 16, 16]} />
        <meshStandardMaterial color={PEPPER_WHITE} roughness={0.3} metalness={0.1} />
      </mesh>

      {/* Eyes */}
      <EyeLED position={[-0.045, 0.1, 0.1]} color={eyeColor} />
      <EyeLED position={[0.045, 0.1, 0.1]} color={eyeColor} />

      {/* Eye sockets (dark recesses) */}
      <mesh position={[-0.045, 0.1, 0.095]}>
        <sphereGeometry args={[0.028, 12, 12]} />
        <meshStandardMaterial color="#2a2a3a" roughness={0.8} />
      </mesh>
      <mesh position={[0.045, 0.1, 0.095]}>
        <sphereGeometry args={[0.028, 12, 12]} />
        <meshStandardMaterial color="#2a2a3a" roughness={0.8} />
      </mesh>

      {/* Mouth speaker grille */}
      <mesh position={[0, 0.04, 0.1]}>
        <boxGeometry args={[0.05, 0.015, 0.01]} />
        <meshStandardMaterial color="#3a3a4a" roughness={0.9} />
      </mesh>

      {/* Camera (forehead, top) */}
      <mesh position={[0, 0.2, 0.06]}>
        <cylinderGeometry args={[0.008, 0.008, 0.01, 12]} />
        <meshStandardMaterial color="#222" roughness={0.5} />
      </mesh>
    </group>
  );
}

function Arm({ side, shoulderPitch, shoulderRoll, elbowYaw, elbowRoll }) {
  const armRef = useRef();
  const forearmRef = useRef();
  const sign = side === 'left' ? 1 : -1;

  useFrame(() => {
    if (armRef.current) {
      armRef.current.rotation.x = -shoulderPitch;
      armRef.current.rotation.z = shoulderRoll;
    }
    if (forearmRef.current) {
      forearmRef.current.rotation.y = elbowYaw;
      forearmRef.current.rotation.z = elbowRoll;
    }
  });

  return (
    <group position={[sign * 0.18, 0.38, 0]}>
      {/* Upper arm */}
      <group ref={armRef}>
        {/* Shoulder sphere */}
        <mesh>
          <sphereGeometry args={[0.05, 16, 16]} />
          <meshStandardMaterial color={PEPPER_WHITE} roughness={0.3} metalness={0.1} />
        </mesh>

        {/* Upper arm cylinder */}
        <mesh position={[0, -0.1, 0]}>
          <capsuleGeometry args={[0.035, 0.12, 8, 16]} />
          <meshStandardMaterial color={PEPPER_LIGHT} roughness={0.3} metalness={0.1} />
        </mesh>

        {/* Elbow joint */}
        <group ref={forearmRef} position={[0, -0.2, 0]}>
          <mesh>
            <sphereGeometry args={[0.035, 12, 12]} />
            <meshStandardMaterial color={PEPPER_DARK} roughness={0.4} />
          </mesh>

          {/* Forearm */}
          <mesh position={[0, -0.1, 0]}>
            <capsuleGeometry args={[0.03, 0.12, 8, 16]} />
            <meshStandardMaterial color={PEPPER_LIGHT} roughness={0.3} metalness={0.1} />
          </mesh>

          {/* Hand sphere */}
          <mesh position={[0, -0.2, 0]}>
            <sphereGeometry args={[0.03, 12, 12]} />
            <meshStandardMaterial color={PEPPER_WHITE} roughness={0.3} />
          </mesh>
        </group>
      </group>
    </group>
  );
}

function Torso({ tabletTexture }) {
  return (
    <group position={[0, 0.15, 0]}>
      {/* Main torso */}
      <mesh position={[0, 0.18, 0]}>
        <capsuleGeometry args={[0.12, 0.2, 12, 24]} />
        <meshStandardMaterial color={PEPPER_WHITE} roughness={0.3} metalness={0.1} />
      </mesh>

      {/* Chest tablet screen */}
      <mesh position={[0, 0.22, 0.12]}>
        <boxGeometry args={[0.18, 0.12, 0.015]} />
        {tabletTexture ? (
          <meshBasicMaterial map={tabletTexture} />
        ) : (
          <meshStandardMaterial
            color={PEPPER_TABLET}
            emissive="#e5e5e0"
            emissiveIntensity={0.05}
            roughness={0.1}
            metalness={0.5}
          />
        )}
      </mesh>

      {/* Tablet bezel */}
      <mesh position={[0, 0.22, 0.115]}>
        <boxGeometry args={[0.19, 0.13, 0.01]} />
        <meshStandardMaterial color="#2a2a2a" roughness={0.8} />
      </mesh>

      {/* Neck cylinder */}
      <mesh position={[0, 0.4, 0]}>
        <cylinderGeometry args={[0.04, 0.05, 0.08, 16]} />
        <meshStandardMaterial color={PEPPER_DARK} roughness={0.4} />
      </mesh>
    </group>
  );
}

function Base({ isMoving }) {
  const baseRef = useRef();

  // Subtle sway when moving
  useFrame((state) => {
    if (baseRef.current && isMoving) {
      baseRef.current.rotation.z = Math.sin(state.clock.elapsedTime * 4) * 0.02;
    }
  });

  return (
    <group ref={baseRef}>
      {/* Hip section */}
      <mesh position={[0, 0.12, 0]}>
        <cylinderGeometry args={[0.1, 0.12, 0.08, 24]} />
        <meshStandardMaterial color={PEPPER_WHITE} roughness={0.3} metalness={0.1} />
      </mesh>

      {/* Leg column */}
      <mesh position={[0, -0.05, 0]}>
        <capsuleGeometry args={[0.06, 0.2, 8, 16]} />
        <meshStandardMaterial color={PEPPER_LIGHT} roughness={0.3} />
      </mesh>

      {/* Base (omni-wheel platform) */}
      <mesh position={[0, -0.22, 0]}>
        <cylinderGeometry args={[0.2, 0.22, 0.06, 32]} />
        <meshStandardMaterial color={PEPPER_WHITE} roughness={0.3} metalness={0.1} />
      </mesh>

      {/* Wheels (decorative) */}
      {[0, 2.094, 4.189].map((angle, i) => (
        <mesh
          key={i}
          position={[
            Math.cos(angle) * 0.18,
            -0.25,
            Math.sin(angle) * 0.18
          ]}
          rotation={[Math.PI / 2, 0, angle]}
        >
          <cylinderGeometry args={[0.025, 0.025, 0.02, 12]} />
          <meshStandardMaterial color="#333" roughness={0.6} />
        </mesh>
      ))}
    </group>
  );
}

function SpeechBubble({ text, position }) {
  if (!text) return null;

  return (
    <group position={[position[0], position[1] + 1.0, position[2]]}>
      <mesh>
        <planeGeometry args={[1.2, 0.3]} />
        <meshBasicMaterial color="#2c2c2e" transparent opacity={0.85} side={THREE.DoubleSide} />
      </mesh>
    </group>
  );
}

export default function PepperModel() {
  const groupRef = useRef();

  const x = usePepperStore((s) => s.x);
  const y = usePepperStore((s) => s.y);
  const theta = usePepperStore((s) => s.theta);
  const joints = usePepperStore((s) => s.joints);
  const eyeColor = usePepperStore((s) => s.eyeColor);
  const isSpeaking = usePepperStore((s) => s.isSpeaking);
  const currentSpeech = usePepperStore((s) => s.currentSpeech);
  const isMoving = usePepperStore((s) => s.isMoving);
  const robotState = usePepperStore((s) => s.robotState);
  const tabletVisible = usePepperStore((s) => s.tabletVisible);
  const tabletUrl = usePepperStore((s) => s.tabletUrl);
  const tabletImage = usePepperStore((s) => s.tabletImage);

  const tabletRenderer = useMemo(() => new TabletRenderer(), []);

  useEffect(() => {
    return () => tabletRenderer.dispose();
  }, [tabletRenderer]);

  useFrame(() => {
    if (groupRef.current) {
      // Map 2D sim coordinates to 3D scene
      groupRef.current.position.x = x - 4;  // center room at origin
      groupRef.current.position.z = y - 3;
      groupRef.current.rotation.y = -theta + Math.PI / 2;
    }
    tabletRenderer.update(robotState, tabletVisible, tabletUrl, tabletImage);
  });

  return (
    <group ref={groupRef}>
      {/* Shadow under base */}
      <mesh position={[0, -0.24, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <circleGeometry args={[0.25, 32]} />
        <meshBasicMaterial color="#000" transparent opacity={0.15} />
      </mesh>

      <Base isMoving={isMoving} />
      <Torso tabletTexture={tabletRenderer.texture} />

      <Arm
        side="left"
        shoulderPitch={joints.LShoulderPitch ?? 1.4}
        shoulderRoll={joints.LShoulderRoll ?? 0.15}
        elbowYaw={joints.LElbowYaw ?? -1.2}
        elbowRoll={joints.LElbowRoll ?? -0.52}
      />
      <Arm
        side="right"
        shoulderPitch={joints.RShoulderPitch ?? 1.4}
        shoulderRoll={joints.RShoulderRoll ?? -0.15}
        elbowYaw={joints.RElbowYaw ?? 1.2}
        elbowRoll={joints.RElbowRoll ?? 0.52}
      />

      <Head
        headYaw={joints.HeadYaw ?? 0}
        headPitch={joints.HeadPitch ?? 0}
        eyeColor={eyeColor}
      />

      <SpeechBubble text={currentSpeech} position={[0, 0, 0]} />
    </group>
  );
}
