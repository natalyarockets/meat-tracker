import { useRef } from 'react';
import { cn } from '@/lib/utils';
import { MarkerType, MarkerPosition } from '@/types/detection';
import { Button } from '@/components/ui/button';
import { Upload, Smartphone, Laptop, Zap, RotateCcw, AlertTriangle } from 'lucide-react';

interface ControlPanelProps {
  modelUrl: string | null;
  phonePosition: MarkerPosition | null;
  laptopPosition: MarkerPosition | null;
  placingMarker: MarkerType;
  isDetected: boolean;
  onFileUpload: (file: File) => void;
  onPlacingMarkerChange: (type: MarkerType) => void;
  onToggleDetection: () => void;
  onReset: () => void;
}

export const ControlPanel = ({
  modelUrl,
  phonePosition,
  laptopPosition,
  placingMarker,
  isDetected,
  onFileUpload,
  onPlacingMarkerChange,
  onToggleDetection,
  onReset,
}: ControlPanelProps) => {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file && file.name.endsWith('.glb')) {
      onFileUpload(file);
    }
  };

  return (
    <div className="glass-panel p-4 space-y-4">
      <h2 className="text-sm font-mono font-semibold text-muted-foreground uppercase tracking-wider">
        Controls
      </h2>
      
      {/* File upload */}
      <div className="space-y-2">
        <input
          ref={fileInputRef}
          type="file"
          accept=".glb"
          onChange={handleFileChange}
          className="hidden"
        />
        <Button
          variant="outline"
          className="w-full justify-start gap-2 border-border/50 hover:bg-secondary hover:border-primary/50"
          onClick={() => fileInputRef.current?.click()}
        >
          <Upload className="w-4 h-4" />
          {modelUrl ? 'Change Room Scan' : 'Upload GLB File'}
        </Button>
        {!modelUrl && (
          <p className="text-xs text-muted-foreground">
            Upload a .glb room scan or use the grid floor
          </p>
        )}
      </div>
      
      {/* Marker placement */}
      <div className="space-y-2">
        <p className="text-xs text-muted-foreground font-mono">Place Markers</p>
        <div className="grid grid-cols-2 gap-2">
          <Button
            variant={placingMarker === 'phone' ? 'default' : 'outline'}
            className={cn(
              "justify-start gap-2",
              placingMarker === 'phone' && "bg-phone text-primary-foreground",
              phonePosition && placingMarker !== 'phone' && "border-phone/50"
            )}
            onClick={() => onPlacingMarkerChange(placingMarker === 'phone' ? null : 'phone')}
          >
            <Smartphone className="w-4 h-4" />
            Phone
            {phonePosition && <span className="ml-auto text-xs">✓</span>}
          </Button>
          <Button
            variant={placingMarker === 'laptop' ? 'default' : 'outline'}
            className={cn(
              "justify-start gap-2",
              placingMarker === 'laptop' && "bg-laptop text-primary-foreground",
              laptopPosition && placingMarker !== 'laptop' && "border-laptop/50"
            )}
            onClick={() => onPlacingMarkerChange(placingMarker === 'laptop' ? null : 'laptop')}
          >
            <Laptop className="w-4 h-4" />
            Laptop
            {laptopPosition && <span className="ml-auto text-xs">✓</span>}
          </Button>
        </div>
        {placingMarker && (
          <p className="text-xs text-primary animate-pulse">
            Click in the 3D scene to place {placingMarker}
          </p>
        )}
      </div>
      
      {/* Demo toggle */}
      <div className="pt-2 border-t border-border/50">
        <Button
          variant={isDetected ? 'destructive' : 'default'}
          className={cn(
            "w-full gap-2 font-mono",
            !isDetected && "bg-accent hover:bg-accent/90 text-accent-foreground"
          )}
          onClick={onToggleDetection}
          disabled={!phonePosition || !laptopPosition}
        >
          {isDetected ? (
            <>
              <AlertTriangle className="w-4 h-4" />
              DETECTION ACTIVE
            </>
          ) : (
            <>
              <Zap className="w-4 h-4" />
              Simulate Detection
            </>
          )}
        </Button>
        {(!phonePosition || !laptopPosition) && (
          <p className="text-xs text-muted-foreground mt-2 text-center">
            Place both markers to enable detection
          </p>
        )}
      </div>
      
      {/* Reset button */}
      <Button
        variant="ghost"
        className="w-full gap-2 text-muted-foreground hover:text-foreground"
        onClick={onReset}
      >
        <RotateCcw className="w-4 h-4" />
        Reset All
      </Button>
    </div>
  );
};
