import React, { useState, useEffect } from 'react';
import { useNairaStore } from '../../../state/useNairaStore';
import FloatingPanel from '../../../ui3d/FloatingPanel';

/**
 * SystemVitalsStrip Component
 * Floating glass strip at the top displaying real-time system vitals, RAM/CPU metrics, and active profile.
 */
export const SystemVitalsStrip = ({ className = '' }) => {
  const userName = useNairaStore((state) => state.userName);
  const userRole = useNairaStore((state) => state.userRole);

  const [cpu, setCpu] = useState(14);
  const [ram, setRam] = useState(42);

  // Simulate subtle real-time vital fluctuations
  useEffect(() => {
    const interval = setInterval(() => {
      setCpu(Math.floor(12 + Math.random() * 10));
      setRam(Math.floor(40 + Math.random() * 5));
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  return (
    <FloatingPanel depth={20} maxTilt={4} className={`px-6 py-2.5 flex items-center justify-between border-cyan-400/20 ${className}`}>
      {/* OS Branding & Operator Badge */}
      <div className="flex items-center gap-3">
        <div className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse shadow-[0_0_10px_#22d3ee]" />
        <div className="flex flex-col">
          <span className="font-mono text-xs font-bold text-cyan-300 tracking-wider">
            NAIRA-OS <span className="text-[10px] text-cyan-500/80 font-normal">v1.0.0</span>
          </span>
          <span className="text-[10px] font-mono text-cyan-400/60 uppercase">
            OPERATOR: {userName} ({userRole})
          </span>
        </div>
      </div>

      {/* Real-time Vitals Metrics */}
      <div className="hidden md:flex items-center gap-6 font-mono text-xs text-cyan-300/80">
        {/* CPU Load */}
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-cyan-500/60 uppercase">CPU</span>
          <div className="w-16 h-1.5 rounded-full bg-slate-900 overflow-hidden border border-cyan-500/20">
            <div className="h-full bg-cyan-400 transition-all duration-500" style={{ width: `${cpu}%` }} />
          </div>
          <span className="text-[11px] font-bold text-cyan-300">{cpu}%</span>
        </div>

        {/* RAM Usage */}
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-cyan-500/60 uppercase">RAM</span>
          <div className="w-16 h-1.5 rounded-full bg-slate-900 overflow-hidden border border-cyan-500/20">
            <div className="h-full bg-emerald-400 transition-all duration-500" style={{ width: `${ram}%` }} />
          </div>
          <span className="text-[11px] font-bold text-cyan-300">{ram}%</span>
        </div>

        {/* Active Engine Modules Count */}
        <div className="flex items-center gap-2 border-l border-cyan-500/20 pl-4">
          <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_#34d399]" />
          <span className="text-[11px] font-semibold text-cyan-200">23 ENGINES ONLINE</span>
        </div>
      </div>

      {/* System Status Indicator */}
      <div className="flex items-center gap-2 text-[10px] font-mono tracking-widest text-cyan-400 uppercase">
        <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
        LIVE_TELEMETRY
      </div>
    </FloatingPanel>
  );
};

export default SystemVitalsStrip;
