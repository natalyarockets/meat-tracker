import { Suspense, useRef } from 'react';
import { Canvas, ThreeEvent } from '@react-three/fiber';
import { OrbitControls, Environment, Grid, PerspectiveCamera, Plane } from '@react-three/drei';
import * as THREE from 'three';
import { SceneProps, MarkerType } from '@/types/detection';
import { Marker } from './Marker';
import { Beam } from './Beam';
import { RoomModel } from './RoomModel';

interface Scene3DProps extends SceneProps {
  placingMarker: MarkerType;
}

const SceneContent = ({
  modelUrl,
  phonePosition,
  laptopPosition,
  isDetected,
  placingMarker,
  onPlaceMarker,
}: Scene3DProps) => {
  const handleFloorClick = (event: ThreeEvent<MouseEvent>) => {
    event.stopPropagation();
    if (!placingMarker) return;
    
    if (event.point) {
      console.log('Floor clicked, placing marker at:', event.point);
      onPlaceMarker(event.point);
    }
  };

  const handleModelClick = (point: THREE.Vector3) => {
    if (!placingMarker) return;
    console.log('Model clicked, placing marker at:', point);
    onPlaceMarker(point);
  };

  return (
    <>
      <PerspectiveCamera makeDefault position={[3, 3, 3]} fov={50} />
      <OrbitControls
        enableDamping
        dampingFactor={0.05}
        minDistance={1}
        maxDistance={20}
        maxPolarAngle={Math.PI / 2}
      />
      
      {/* Lighting */}
      <ambientLight intensity={0.5} />
      <directionalLight
        position={[5, 10, 5]}
        intensity={1}
        castShadow
        shadow-mapSize={[2048, 2048]}
      />
      <pointLight position={[-5, 5, -5]} intensity={0.5} color="#00d4ff" />
      <pointLight position={[5, 5, 5]} intensity={0.3} color="#ffffff" />
      
      {/* Environment */}
      <Environment preset="night" />
      
      {/* Grid floor when no model */}
      {!modelUrl && (
        <>
          <Grid
            position={[0, -0.01, 0]}
            args={[10, 10]}
            cellSize={0.5}
            cellThickness={0.5}
            cellColor="#1e3a5f"
            sectionSize={2}
            sectionThickness={1}
            sectionColor="#2563eb"
            fadeDistance={15}
            fadeStrength={1}
            followCamera={false}
          />
          {/* Clickable floor plane */}
          <Plane
            args={[20, 20]}
            rotation={[-Math.PI / 2, 0, 0]}
            position={[0, 0, 0]}
            onClick={handleFloorClick}
          >
            <meshBasicMaterial transparent opacity={0} side={THREE.DoubleSide} />
          </Plane>
        </>
      )}
      
      {/* Room model */}
      {modelUrl && (
        <Suspense fallback={
          <mesh>
            <boxGeometry args={[1, 1, 1]} />
            <meshStandardMaterial color="#00d4ff" wireframe />
          </mesh>
        }>
          <RoomModel url={modelUrl} onClick={handleModelClick} />
          {/* Add a floor plane for clicking even with model */}
          <Plane
            args={[20, 20]}
            rotation={[-Math.PI / 2, 0, 0]}
            position={[0, -0.5, 0]}
            onClick={handleFloorClick}
          >
            <meshBasicMaterial transparent opacity={0} side={THREE.DoubleSide} />
          </Plane>
        </Suspense>
      )}
      
      {/* Markers */}
      {phonePosition && (
        <Marker position={phonePosition} type="phone" isDetected={isDetected} />
      )}
      {laptopPosition && (
        <Marker position={laptopPosition} type="laptop" isDetected={isDetected} />
      )}
      
      {/* Beam between markers */}
      {phonePosition && laptopPosition && (
        <Beam start={phonePosition} end={laptopPosition} isDetected={isDetected} />
      )}
    </>
  );
};

export const Scene3D = (props: Scene3DProps) => {
  return (
    <div className="w-full h-full bg-background rounded-lg overflow-hidden">
      <Canvas
        shadows
        gl={{
          antialias: true,
          toneMapping: THREE.ACESFilmicToneMapping,
          toneMappingExposure: 1.2,
        }}
        style={{ background: 'linear-gradient(180deg, hsl(220 20% 8%) 0%, hsl(220 20% 4%) 100%)' }}
      >
        <SceneContent {...props} />
      </Canvas>
    </div>
  );
};
