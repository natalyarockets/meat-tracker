import * as THREE from 'three';

export interface MarkerPosition {
  x: number;
  y: number;
  z: number;
}

export interface DetectionState {
  isDetected: boolean;
  rssi: number;
  baseline: number;
  phonePosition: MarkerPosition | null;
  laptopPosition: MarkerPosition | null;
}

export type MarkerType = 'phone' | 'laptop' | null;

export interface SceneProps {
  modelUrl: string | null;
  phonePosition: MarkerPosition | null;
  laptopPosition: MarkerPosition | null;
  isDetected: boolean;
  placingMarker: MarkerType;
  onPlaceMarker: (position: THREE.Vector3) => void;
}
