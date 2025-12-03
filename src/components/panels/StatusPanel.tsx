import { cn } from '@/lib/utils';
import { DetectionState } from '@/types/detection';
import { Wifi, WifiOff, Activity, AlertTriangle } from 'lucide-react';

interface StatusPanelProps {
  state: DetectionState;
}

export const StatusPanel = ({ state }: StatusPanelProps) => {
  const { isDetected, rssi, baseline } = state;
  
  const rssiDelta = rssi - baseline;
  const signalStrength = Math.min(100, Math.max(0, (rssi + 100) * 1.5));

  return (
    <div className={cn(
      "glass-panel p-4 space-y-4 transition-all duration-300",
      isDetected && "ring-2 ring-destructive/50"
    )}>
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-mono font-semibold text-muted-foreground uppercase tracking-wider">
          Detection Status
        </h2>
        {isDetected ? (
          <WifiOff className="w-4 h-4 text-destructive animate-pulse" />
        ) : (
          <Wifi className="w-4 h-4 text-accent" />
        )}
      </div>
      
      {/* Status indicator */}
      <div className={cn(
        "flex items-center gap-3 p-3 rounded-md transition-all duration-300",
        isDetected ? "bg-destructive/20 animate-pulse" : "bg-accent/10"
      )}>
        <div className={cn(
          "status-indicator",
          isDetected ? "status-detected" : "status-clear"
        )} />
        <div className="flex items-center gap-2">
          {isDetected && <AlertTriangle className="w-4 h-4 text-destructive" />}
          <span className={cn(
            "font-mono font-bold text-lg",
            isDetected ? "text-destructive" : "text-accent"
          )}>
            {isDetected ? 'DETECTED' : 'CLEAR'}
          </span>
        </div>
      </div>
      
      {/* Metrics */}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-secondary/50 rounded-md p-3">
          <div className="flex items-center gap-2 mb-1">
            <Activity className="w-3 h-3 text-primary" />
            <span className="text-xs font-mono text-muted-foreground">RSSI</span>
          </div>
          <div className="font-mono font-bold text-xl text-foreground">
            {rssi} <span className="text-xs text-muted-foreground">dBm</span>
          </div>
        </div>
        
        <div className="bg-secondary/50 rounded-md p-3">
          <div className="flex items-center gap-2 mb-1">
            <div className="w-3 h-3 rounded-full bg-primary/50" />
            <span className="text-xs font-mono text-muted-foreground">Baseline</span>
          </div>
          <div className="font-mono font-bold text-xl text-foreground">
            {baseline} <span className="text-xs text-muted-foreground">dBm</span>
          </div>
        </div>
      </div>
      
      {/* Signal strength bar */}
      <div className="space-y-2">
        <div className="flex justify-between text-xs font-mono text-muted-foreground">
          <span>Signal Strength</span>
          <span>{signalStrength.toFixed(0)}%</span>
        </div>
        <div className="h-2 bg-secondary rounded-full overflow-hidden">
          <div
            className={cn(
              "h-full rounded-full transition-all duration-500",
              isDetected ? "bg-destructive animate-pulse" : "bg-gradient-to-r from-primary to-accent"
            )}
            style={{ width: `${signalStrength}%` }}
          />
        </div>
      </div>
      
      {/* Delta indicator */}
      <div className={cn(
        "text-center py-2 rounded-md font-mono text-sm transition-all duration-300",
        rssiDelta > 5 ? "bg-destructive/20 text-destructive" :
        rssiDelta < -5 ? "bg-accent/20 text-accent" :
        "bg-secondary text-muted-foreground"
      )}>
        Δ {rssiDelta > 0 ? '+' : ''}{rssiDelta} dBm from baseline
      </div>
    </div>
  );
};
