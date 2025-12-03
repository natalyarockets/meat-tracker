import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import { Sphere, Html } from '@react-three/drei';
import * as THREE from 'three';
import { MarkerPosition } from '@/types/detection';

interface MarkerProps {
  position: MarkerPosition;
  type: 'phone' | 'laptop';
  isDetected?: boolean;
}

export const Marker = ({ position, type, isDetected = false }: MarkerProps) => {
  const meshRef = useRef<THREE.Mesh>(null);
  const glowRef = useRef<THREE.Mesh>(null);
  
  const isPhone = type === 'phone';
  const baseColor = isPhone ? '#3b82f6' : '#22c55e';
  const alertColor = '#ef4444';
  const color = isDetected && isPhone ? alertColor : baseColor;
  
  useFrame((state) => {
    if (meshRef.current) {
      // Subtle floating animation
      meshRef.current.position.y = position.y + Math.sin(state.clock.elapsedTime * 2) * 0.02;
    }
    if (glowRef.current) {
      // Pulsing glow
      const scale = 1 + Math.sin(state.clock.elapsedTime * 3) * 0.1;
      glowRef.current.scale.setScalar(scale);
    }
  });

  return (
    <group position={[position.x, position.y, position.z]}>
      {/* Glow sphere */}
      <Sphere ref={glowRef} args={[0.15, 16, 16]}>
        <meshBasicMaterial
          color={color}
          transparent
          opacity={0.3}
        />
      </Sphere>
      
      {/* Main sphere */}
      <Sphere ref={meshRef} args={[0.08, 32, 32]} position={[0, 0, 0]}>
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={0.5}
          metalness={0.8}
          roughness={0.2}
        />
      </Sphere>
      
      {/* Label */}
      <Html
        position={[0, 0.25, 0]}
        center
        style={{
          pointerEvents: 'none',
        }}
      >
        <div className="glass-panel px-2 py-1 text-xs font-mono whitespace-nowrap">
          <span style={{ color }}>{isPhone ? '📱 Phone' : '💻 Laptop'}</span>
        </div>
      </Html>
    </group>
  );
};
