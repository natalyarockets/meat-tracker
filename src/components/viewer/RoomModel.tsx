import { useEffect, useMemo } from 'react';
import { useGLTF } from '@react-three/drei';
import { ThreeEvent } from '@react-three/fiber';
import * as THREE from 'three';

interface RoomModelProps {
  url: string;
  onClick: (point: THREE.Vector3) => void;
}

export const RoomModel = ({ url, onClick }: RoomModelProps) => {
  const { scene } = useGLTF(url);
  
  // Clone the scene to prevent issues with reuse
  const clonedScene = useMemo(() => {
    const clone = scene.clone(true);
    return clone;
  }, [scene]);
  
  useEffect(() => {
    if (clonedScene) {
      // Center and scale the model
      const box = new THREE.Box3().setFromObject(clonedScene);
      const center = box.getCenter(new THREE.Vector3());
      const size = box.getSize(new THREE.Vector3());
      
      const maxDim = Math.max(size.x, size.y, size.z);
      const scale = 3 / maxDim;
      
      clonedScene.scale.setScalar(scale);
      clonedScene.position.sub(center.multiplyScalar(scale));
      
      // Make all meshes clickable and receive shadows
      clonedScene.traverse((child) => {
        if (child instanceof THREE.Mesh) {
          child.castShadow = true;
          child.receiveShadow = true;
          
          // Enhance materials for better visibility
          if (child.material) {
            const mat = child.material as THREE.MeshStandardMaterial;
            if (mat.roughness !== undefined) {
              mat.roughness = 0.7;
              mat.metalness = 0.1;
            }
          }
        }
      });
      
      console.log('GLB model loaded and processed');
    }
  }, [clonedScene]);

  const handleClick = (event: ThreeEvent<MouseEvent>) => {
    event.stopPropagation();
    if (event.point) {
      console.log('Model clicked at:', event.point);
      onClick(event.point);
    }
  };

  return (
    <primitive
      object={clonedScene}
      onClick={handleClick}
    />
  );
};
