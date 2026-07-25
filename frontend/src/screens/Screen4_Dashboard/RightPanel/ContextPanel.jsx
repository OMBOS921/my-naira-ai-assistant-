import React, { useState } from 'react';
import FloatingPanel from '../../../ui3d/FloatingPanel';

/**
 * ContextPanel Component
 * Tabbed floating 3D glass panel for real-time LiveFeed, Memory, Security, and Vision telemetry.
 */
export const ContextPanel = ({ className = '' }) => {
  const [activeTab, setActiveTab] = useState('feed');

  const tabs = [
    { id: 'feed', label: 'Telemetry' },
    { id: 'memory', label: 'Memory' },
    { id: 'security', label: 'Security' },
    { id: 'vision', label: 'Vision' },
  ];

  return (
    <FloatingPanel depth={30} maxTilt={8} className={`p-4 flex flex-col gap-3 w-80 border-cyan-400/20 ${className}`}>
      {/* Header & Tabs */}
      <div className="flex items-center justify-between border-b border-cyan-500/20 pb-2">
        <div className="flex gap-1 bg-slate-950/60 p-1 rounded-xl border border-cyan-500/20 w-full">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex-1 py-1 text-[10px] font-mono tracking-wider rounded-lg transition-all cursor-pointer ${
                activeTab === tab.id
                  ? 'bg-cyan-500/20 text-cyan-200 border border-cyan-400/40 font-bold shadow-[0_0_8px_rgba(34,211,238,0.3)]'
                  : 'text-slate-400 hover:text-cyan-300'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab Content Display */}
      <div className="h-64 overflow-y-auto pr-1 flex flex-col gap-2 font-mono text-xs text-cyan-200">
        {activeTab === 'feed' && <LiveFeedTab />}
        {activeTab === 'memory' && <MemoryTab />}
        {activeTab === 'security' && <SecurityTab />}
        {activeTab === 'vision' && <VisionTab />}
      </div>
    </FloatingPanel>
  );
};

/* Tab 1: Live Telemetry Feed */
const LiveFeedTab = () => {
  const logs = [
    { time: '12:37:40', text: '[INFO] Audio spectrum analyzer online', type: 'info' },
    { time: '12:37:42', text: '[OK] Gemini 1.5 Pro pipeline connected', type: 'ok' },
    { time: '12:37:45', text: '[STREAM] Telemetry buffer active', type: 'info' },
    { time: '12:37:48', text: '[AGENT] Coder Agent spawned worker', type: 'agent' },
    { time: '12:37:50', text: '[SEC] Sandbox permissions validated', type: 'sec' },
  ];

  return (
    <div className="flex flex-col gap-2 text-[11px]">
      {logs.map((log, index) => (
        <div key={index} className="p-2 rounded-lg bg-slate-950/50 border border-cyan-500/10 flex flex-col gap-0.5">
          <span className="text-[9px] text-cyan-500/60">{log.time}</span>
          <span className="text-cyan-200 leading-tight">{log.text}</span>
        </div>
      ))}
    </div>
  );
};

/* Tab 2: Memory Store */
const MemoryTab = () => (
  <div className="flex flex-col gap-2 text-[11px]">
    <div className="p-2 rounded-lg bg-slate-950/50 border border-cyan-500/10">
      <span className="text-[9px] text-cyan-500/60 uppercase">VECTOR EMBEDDING INDEX</span>
      <p className="text-cyan-200 mt-1">1,420 conversation fragments indexed</p>
    </div>
    <div className="p-2 rounded-lg bg-slate-950/50 border border-cyan-500/10">
      <span className="text-[9px] text-cyan-500/60 uppercase">ACTIVE SESSION CONTEXT</span>
      <p className="text-cyan-200 mt-1">User identity: Lead Architect (Boss)</p>
    </div>
    <div className="p-2 rounded-lg bg-slate-950/50 border border-cyan-500/10">
      <span className="text-[9px] text-cyan-500/60 uppercase">SHORT-TERM MEMORY DENSITY</span>
      <p className="text-emerald-300 mt-1">Optimal (98.4% retention accuracy)</p>
    </div>
  </div>
);

/* Tab 3: Security & Cryptography */
const SecurityTab = () => (
  <div className="flex flex-col gap-2 text-[11px]">
    <div className="p-2 rounded-lg bg-emerald-950/30 border border-emerald-500/20 text-emerald-300">
      <span className="text-[9px] uppercase tracking-wider font-bold">CRYPTO GATEWAY ACTIVE</span>
      <p className="mt-0.5 text-[10px]">RSA-4096 / TLS 1.3 Encryption verified</p>
    </div>
    <div className="p-2 rounded-lg bg-slate-950/50 border border-cyan-500/10">
      <span className="text-[9px] text-cyan-500/60 uppercase">SANDBOX ISOLATION</span>
      <p className="text-cyan-200 mt-0.5">Strict process scoping enforced</p>
    </div>
    <div className="p-2 rounded-lg bg-slate-950/50 border border-cyan-500/10">
      <span className="text-[9px] text-cyan-500/60 uppercase">API KEYS VAULT</span>
      <p className="text-cyan-300 mt-0.5">Gemini API Key: [CONFIGURED]</p>
    </div>
  </div>
);

/* Tab 4: Spatial Vision Monitor */
const VisionTab = () => (
  <div className="flex flex-col gap-2 text-[11px]">
    <div className="relative w-full h-32 rounded-lg bg-slate-950 border border-cyan-500/30 overflow-hidden flex items-center justify-center">
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#06b6d415_1px,transparent_1px),linear-gradient(to_bottom,#06b6d415_1px,transparent_1px)] bg-[size:1rem_1rem]" />
      <span className="text-[10px] text-cyan-400 font-mono tracking-widest animate-pulse z-10">
        [SPATIAL CAMERA FEED ONLINE]
      </span>
    </div>
    <div className="flex justify-between items-center text-[10px] text-cyan-400/80">
      <span>FRAME RATE: 60 FPS</span>
      <span>RESOLUTION: 1080P</span>
    </div>
  </div>
);

export default ContextPanel;
