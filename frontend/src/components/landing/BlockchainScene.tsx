"use client";

// Interactive 3D "audit chain": blocks as connected nodes, with a mining pulse
// travelling along the chain. Loaded only via next/dynamic (ssr:false) and only
// once scrolled into view — see BlockchainCanvas. Kept deliberately lightweight
// (few nodes, no post-processing) so it stays smooth on a mid-range phone.

import { useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Line } from "@react-three/drei";
import * as THREE from "three";

const N = 9;
const RADIUS = 1.7;
const STEP = 0.62;

function nodePositions(): [number, number, number][] {
  const pts: [number, number, number][] = [];
  for (let i = 0; i < N; i++) {
    const a = i * 0.7;
    const y = i * STEP - (N * STEP) / 2;
    pts.push([Math.cos(a) * RADIUS, y, Math.sin(a) * RADIUS]);
  }
  return pts;
}

function Block({ position, index }: { position: [number, number, number]; index: number }) {
  const ref = useRef<THREE.Mesh>(null);
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    // A pulse of "mining" activity travels up the chain.
    const phase = (t * 0.9) % N;
    const dist = Math.abs(((index - phase + N) % N));
    const near = Math.max(0, 1 - dist / 1.6);
    if (ref.current) {
      const mat = ref.current.material as THREE.MeshStandardMaterial;
      mat.emissiveIntensity = 0.25 + near * 1.6;
      const s = 1 + near * 0.18;
      ref.current.scale.setScalar(s);
    }
  });
  return (
    <mesh ref={ref} position={position}>
      <boxGeometry args={[0.42, 0.42, 0.42]} />
      <meshStandardMaterial
        color="#0e2038"
        emissive="#22d3ee"
        emissiveIntensity={0.3}
        metalness={0.6}
        roughness={0.25}
      />
    </mesh>
  );
}

function Chain() {
  const group = useRef<THREE.Group>(null);
  const positions = useMemo(() => nodePositions(), []);
  useFrame((_, delta) => {
    if (group.current) group.current.rotation.y += delta * 0.18;
  });
  return (
    <group ref={group}>
      <Line points={positions} color="#2f81f7" lineWidth={1.2} transparent opacity={0.5} />
      {positions.map((p, i) => (
        <Block key={i} position={p} index={i} />
      ))}
    </group>
  );
}

export default function BlockchainScene() {
  return (
    <Canvas
      camera={{ position: [0, 0, 6.2], fov: 50 }}
      dpr={[1, 1.6]}
      gl={{ antialias: true, alpha: true }}
      style={{ background: "transparent" }}
    >
      <ambientLight intensity={0.5} />
      <pointLight position={[4, 6, 5]} intensity={60} color="#2f81f7" />
      <pointLight position={[-5, -3, 2]} intensity={30} color="#22d3ee" />
      <Chain />
    </Canvas>
  );
}
