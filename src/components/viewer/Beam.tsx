import { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import { Line } from '@react-three/drei';
import * as THREE from 'three';
import { MarkerPosition } from '@/types/detection';

interface BeamProps {
  start: MarkerPosition;
  end: MarkerPosition;
  isDetected: boolean;
}

export const Beam = ({ start, end, isDetected }: BeamProps) => {
  const tubeRef = useRef<THREE.Mesh>(null);
  
  const clearColor = '#00d4ff';
  const detectedColor = '#ef4444';
  
  const { curve, points } = useMemo(() => {
    const startVec = new THREE.Vector3(start.x, start.y, start.z);
    const endVec = new THREE.Vector3(end.x, end.y, end.z);
    
    // Create a slight arc for visual interest
    const midPoint = new THREE.Vector3().lerpVectors(startVec, endVec, 0.5);
    midPoint.y += 0.1;
    
    const curve = new THREE.QuadraticBezierCurve3(startVec, midPoint, endVec);
    const points = curve.getPoints(50);
    
    return { curve, points };
  }, [start, end]);

  const tubeGeometry = useMemo(() => {
    return new THREE.TubeGeometry(curve, 50, 0.015, 8, false);
  }, [curve]);

  const currentColor = isDetected ? detectedColor : clearColor;

  useFrame((state) => {
    if (tubeRef.current) {
      const material = tubeRef.current.material as THREE.MeshBasicMaterial;
      if (isDetected) {
        material.opacity = 0.4 + Math.sin(state.clock.elapsedTime * 8) * 0.3;
      } else {
        material.opacity = 0.6;
      }
    }
  });

  return (
    <group>
      {/* Outer glow tube */}
      <mesh ref={tubeRef} geometry={tubeGeometry}>
        <meshBasicMaterial
          color={currentColor}
          transparent
          opacity={0.6}
          side={THREE.DoubleSide}
        />
      </mesh>
      
      {/* Core beam line using drei Line */}
      <Line
        points={points.map(p => [p.x, p.y, p.z] as [number, number, number])}
        color={currentColor}
        lineWidth={2}
        transparent
        opacity={0.9}
      />
      
      {/* Particle effect dots along beam */}
      {points.filter((_, i) => i % 5 === 0).map((point, i) => (
        <mesh key={i} position={[point.x, point.y, point.z]}>
          <sphereGeometry args={[0.008, 8, 8]} />
          <meshBasicMaterial
            color={currentColor}
            transparent
            opacity={0.6}
          />
        </mesh>
      ))}
    </group>
  );
};
