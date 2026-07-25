import React from 'react';
import AvatarStage from '../../avatar/AvatarStage';
import EngineOrbitRing from './EngineOrbitRing';
import BootProgressRing from './BootProgressRing';

const MOCK_ENGINES = [
  { id: 1, name: 'AutonomousTaskEngine', status: 'ok' },
  { id: 2, name: 'VisionModule', status: 'ok' },
  { id: 3, name: 'VectorMemoryDB', status: 'ok' },
  { id: 4, name: 'TTS_Synthesizer', status: 'ok' },
  { id: 5, name: 'LLM_Router', status: 'ok' },
  { id: 6, name: 'AudioStreamPipeline', status: 'pending' },
  { id: 7, name: 'IntentClassifier', status: 'ok' },
  { id: 8, name: 'ActionPlanner', status: 'ok' },
  { id: 9, name: 'KnowledgeGraph', status: 'ok' },
  { id: 10, name: 'VoiceActivityDetector', status: 'ok' },
  { id: 11, name: 'SystemMonitor', status: 'ok' },
  { id: 12, name: 'EventBusHub', status: 'ok' },
  { id: 13, name: 'PluginHostContainer', status: 'pending' },
  { id: 14, name: 'SecurityGateway', status: 'ok' },
  { id: 15, name: 'HardwareAbstraction', status: 'ok' },
  { id: 16, name: 'PersonaMatrix', status: 'ok' },
  { id: 17, name: 'ContextCache', status: 'ok' },
  { id: 18, name: 'EmotionEngine', status: 'ok' },
  { id: 19, name: 'SpeechRecognition', status: 'pending' },
  { id: 20, name: 'RealtimeTelemetry', status: 'ok' },
  { id: 21, name: 'HolographicRenderer', status: 'ok' },
];

/**
 * BootScreen Orchestrator Component (Screen 1)
 * Displays the holographic 3D boot sequence with 21 orbital engines around the avatar stage.
 */
export const BootScreen = ({ onBootComplete }) => {
  return (
    <div className="perspective-stage w-full h-full relative flex flex-col justify-between items-center p-6 overflow-hidden bg-[#0A0E27] text-white select-none">
      {/* Background Cyber Grid */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#1f293715_1px,transparent_1px),linear-gradient(to_bottom,#1f293715_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_50%,#000_70%,transparent_100%)] pointer-events-none" />

      {/* Top Futuristic Header Overlay */}
      <header className="z-30 w-full max-w-6xl mx-auto flex justify-between items-center border-b border-cyan-500/20 pb-4 shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse shadow-[0_0_10px_#22d3ee]" />
          <h1 className="text-lg font-bold font-mono tracking-widest text-cyan-300">
            NAIRA-OS
          </h1>
        </div>
        <div className="text-xs font-mono text-cyan-300 tracking-widest uppercase flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400" />
          SYSTEM_BOOT_ACTIVE
        </div>
      </header>

      {/* Main 3D Stage Container */}
      <div className="relative flex items-center justify-center preserve-3d w-full flex-1">
        {/* Orbital Engine Nodes (Midground / Background) */}
        <EngineOrbitRing engines={MOCK_ENGINES} radius={360} className="z-0" />

        {/* Central Avatar Stage (Mic button disabled for Boot sequence) */}
        <AvatarStage size="lg" showMic={false} className="z-10" />
      </div>

      {/* Bottom Floating Progress Ring HUD */}
      <BootProgressRing onBootComplete={onBootComplete} className="z-20 shrink-0 mb-4" />
    </div>
  );
};

export default BootScreen;
