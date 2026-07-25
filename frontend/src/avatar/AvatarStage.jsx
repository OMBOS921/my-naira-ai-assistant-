import React from 'react';
import { motion } from 'framer-motion';
import { useNairaStore } from '../state/useNairaStore';
import { useNeuralMic } from '../hooks/useNeuralMic';
import { ACTIVE_AVATAR_RENDERER, AVATAR_RENDERERS } from './avatarConfig';

const SIZE_MAP = {
  sm: 'w-36 h-36',
  md: 'w-56 h-56',
  lg: 'w-72 h-72 md:w-80 md:h-80',
  xl: 'w-[400px] h-[400px]',
};

/**
 * ConcentricDataRing Component
 * Perfectly concentric ticking data ring anchored directly to the center of the avatar container.
 * Features 36 radial tick marks, outer segmented arcs, cardinal pulse nodes, and vibrant glowing green active state animations.
 */
const ConcentricDataRing = ({ isMicActive, isSpeaking }) => {
  const isActive = isMicActive || isSpeaking;
  const activeColor = '#34d399'; // Vibrant Glowing Emerald Green
  const inactiveColor = '#06b6d4'; // Tactical Cyan

  // Generate 36 radial tick marks around 360 degrees
  const ticks = Array.from({ length: 36 }).map((_, i) => {
    const angle = (i * 360) / 36;
    const isMajor = i % 3 === 0;
    const innerR = isMajor ? 204 : 210;
    const outerR = 222;
    const rad = (angle * Math.PI) / 180;
    const x1 = 240 + innerR * Math.cos(rad);
    const y1 = 240 + innerR * Math.sin(rad);
    const x2 = 240 + outerR * Math.cos(rad);
    const y2 = 240 + outerR * Math.sin(rad);
    return { angle, isMajor, x1, y1, x2, y2 };
  });

  return (
    <motion.div
      animate={
        isActive
          ? {
              scale: [1, 1.035, 1],
              opacity: [0.85, 1, 0.85],
              filter: [
                'drop-shadow(0 0 10px #34d399) blur(0px)',
                'drop-shadow(0 0 22px #34d399) blur(1px)',
                'drop-shadow(0 0 10px #34d399) blur(0px)',
              ],
            }
          : {
              scale: [1, 1.01, 1],
              opacity: [0.45, 0.65, 0.45],
              filter: 'drop-shadow(0 0 5px rgba(6,182,212,0.3)) blur(0px)',
            }
      }
      transition={{
        duration: isActive ? 1.2 : 3,
        repeat: Infinity,
        ease: 'easeInOut',
      }}
      className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[480px] h-[480px] pointer-events-none z-10"
    >
      <svg viewBox="0 0 480 480" className="w-full h-full">
        {/* Outer Circular Track Line */}
        <circle
          cx="240"
          cy="240"
          r="230"
          fill="none"
          stroke={isActive ? activeColor : '#0891b2'}
          strokeWidth={isActive ? '2' : '1.5'}
          strokeOpacity={isActive ? '0.9' : '0.35'}
          strokeDasharray="8 4 2 4"
        />

        {/* Inner Ticking Track Baseline */}
        <circle
          cx="240"
          cy="240"
          r="202"
          fill="none"
          stroke={isActive ? activeColor : inactiveColor}
          strokeWidth="1.5"
          strokeOpacity={isActive ? '0.75' : '0.3'}
        />

        {/* 36 Radial Ticks around the circle */}
        {ticks.map((tick, i) => (
          <line
            key={i}
            x1={tick.x1}
            y1={tick.y1}
            x2={tick.x2}
            y2={tick.y2}
            stroke={isActive ? activeColor : inactiveColor}
            strokeWidth={tick.isMajor ? (isActive ? '3' : '2') : '1.5'}
            strokeOpacity={tick.isMajor ? (isActive ? '1' : '0.7') : isActive ? '0.85' : '0.4'}
            strokeLinecap="round"
          />
        ))}

        {/* Outer Segment Arcs */}
        <path
          d="M 240,10 A 230,230 0 0,1 470,240"
          fill="none"
          stroke={isActive ? activeColor : inactiveColor}
          strokeWidth={isActive ? '3' : '2'}
          strokeOpacity={isActive ? '0.9' : '0.4'}
          strokeDasharray="45 15 25 15"
        />
        <path
          d="M 240,470 A 230,230 0 0,1 10,240"
          fill="none"
          stroke={isActive ? activeColor : inactiveColor}
          strokeWidth={isActive ? '3' : '2'}
          strokeOpacity={isActive ? '0.9' : '0.4'}
          strokeDasharray="45 15 25 15"
        />

        {/* Active Cardinal Pulse Dots */}
        {isActive && (
          <>
            <circle cx="240" cy="10" r="4" fill={activeColor} className="animate-ping" />
            <circle cx="470" cy="240" r="4" fill={activeColor} className="animate-ping" />
            <circle cx="240" cy="470" r="4" fill={activeColor} className="animate-ping" />
            <circle cx="10" cy="240" r="4" fill={activeColor} className="animate-ping" />
          </>
        )}
      </svg>
    </motion.div>
  );
};

export const AvatarStage = ({ size = 'lg', showMic = false, className = '' }) => {
  const avatarMode = useNairaStore((state) => state.avatarMode);
  const { isMicListening, toggleListening } = useNeuralMic();

  // Dynamic Renderer resolution from Adapter Strategy Registry
  const RendererComponent = AVATAR_RENDERERS[ACTIVE_AVATAR_RENDERER] || AVATAR_RENDERERS.video;

  const sizeClass = SIZE_MAP[size] || SIZE_MAP.lg;
  const isMicActive = isMicListening || avatarMode === 'listening';
  const isSpeaking = avatarMode === 'speaking';
  const isActive = isMicActive || isSpeaking;

  const handleMicToggle = () => {
    toggleListening();
  };

  return (
    <div className={`relative flex flex-col items-center justify-center -translate-y-2 ${className}`}>
      {/* Primary Concentric Assembly Anchor Container */}
      <div className="relative flex items-center justify-center">
        {/* Layer 0: Background Ambient Glow & Energy Pulse Wave */}
        <motion.div
          animate={
            isActive
              ? { scale: [1, 1.14, 1], opacity: [0.3, 0.75, 0.3] }
              : { scale: [1, 1.04, 1], opacity: [0.1, 0.25, 0.1] }
          }
          transition={{ duration: isActive ? 1.5 : 3, repeat: Infinity, ease: 'easeInOut' }}
          className={`absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[510px] h-[510px] rounded-full pointer-events-none z-0 border ${
            isActive
              ? 'border-emerald-400/40 shadow-[0_0_65px_rgba(52,211,153,0.35)]'
              : 'border-cyan-500/20'
          }`}
        />

        {/* Layer 10: Large Concentric Ticking Data Ring (directly behind Avatar circle) */}
        <ConcentricDataRing isMicActive={isMicActive} isSpeaking={isSpeaking} />

        {/* Layer 20: Floating Tactical HUD Readouts (Data Overlays) */}
        <div className="absolute inset-0 pointer-events-none z-20 hidden md:block">
          {/* Top-Left Readout */}
          <motion.div
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            className={`absolute -top-6 -left-16 flex items-center gap-1.5 font-mono text-[10px] tracking-wider px-2.5 py-1 rounded-md border backdrop-blur-md transition-all duration-300 shadow-md ${
              isActive
                ? 'text-emerald-300 bg-slate-950/90 border-emerald-500/50 shadow-[0_0_12px_rgba(52,211,153,0.3)]'
                : 'text-cyan-400/80 bg-slate-950/70 border-cyan-500/30'
            }`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${isActive ? 'bg-emerald-400 animate-ping' : 'bg-cyan-400'}`} />
            <span>AURA RESONANCE: {isActive ? 'OPTIMAL' : 'STABLE'}</span>
          </motion.div>

          {/* Top-Right Readout */}
          <motion.div
            initial={{ opacity: 0, x: 10 }}
            animate={{ opacity: 1, x: 0 }}
            className={`absolute -top-6 -right-16 flex items-center gap-1.5 font-mono text-[10px] tracking-wider px-2.5 py-1 rounded-md border backdrop-blur-md transition-all duration-300 shadow-md ${
              isActive
                ? 'text-emerald-300 bg-slate-950/90 border-emerald-500/50 shadow-[0_0_12px_rgba(52,211,153,0.3)]'
                : 'text-cyan-400/80 bg-slate-950/70 border-cyan-500/30'
            }`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${isActive ? 'bg-emerald-400 animate-pulse' : 'bg-cyan-400'}`} />
            <span>NEURAL LINK: 99.8%</span>
          </motion.div>

          {/* Mid-Right Tactical Indicator */}
          <div
            className={`absolute top-1/2 -right-24 -translate-y-1/2 flex items-center gap-1.5 font-mono text-[9px] tracking-widest px-2 py-0.5 rounded border ${
              isActive
                ? 'text-emerald-400/90 border-emerald-500/40 bg-slate-950/80 shadow-[0_0_8px_rgba(52,211,153,0.2)]'
                : 'text-cyan-500/60 border-cyan-500/20 bg-slate-950/60'
            }`}
          >
            <span>[ FREQ: 432Hz ]</span>
          </div>

          {/* Mid-Left Tactical Indicator */}
          <div
            className={`absolute top-1/2 -left-24 -translate-y-1/2 flex items-center gap-1.5 font-mono text-[9px] tracking-widest px-2 py-0.5 rounded border ${
              isActive
                ? 'text-emerald-400/90 border-emerald-500/40 bg-slate-950/80 shadow-[0_0_8px_rgba(52,211,153,0.2)]'
                : 'text-cyan-500/60 border-cyan-500/20 bg-slate-950/60'
            }`}
          >
            <span>[ RING: SYNCED ]</span>
          </div>
        </div>

        {/* Layer 30: Foreground Avatar Circle Container */}
        <div
          className={`relative rounded-full p-1 transition-all duration-500 z-30 ${
            isActive
              ? 'bg-gradient-to-b from-emerald-400/60 via-emerald-600/30 to-emerald-400/60 shadow-[0_0_45px_rgba(52,211,153,0.5)]'
              : 'bg-gradient-to-b from-cyan-500/40 via-indigo-500/20 to-cyan-500/40 shadow-[0_0_35px_rgba(6,182,212,0.3)]'
          } backdrop-blur-md ${sizeClass}`}
        >
          {/* Active Renderer Component */}
          {RendererComponent ? (
            <RendererComponent mode={avatarMode} className="w-full h-full rounded-full overflow-hidden" />
          ) : (
            <div className="w-full h-full rounded-full bg-slate-900 flex items-center justify-center text-cyan-400 text-sm">
              Renderer Unavailable
            </div>
          )}

          {/* Holographic Scanlines Effect */}
          <div className="pointer-events-none absolute inset-0 rounded-full bg-[linear-gradient(rgba(18,16,16,0)_50%,rgba(0,255,255,0.05)_50%)] bg-[length:100%_4px] opacity-40" />
        </div>
      </div>

      {/* Layer 40: Central Tactical Microphone Button & Status Panel */}
      {showMic && (
        <div className="mt-5 flex flex-col items-center gap-2.5 z-40">
          {/* Metallic Bezel Outer Housing */}
          <motion.button
            type="button"
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.94 }}
            onClick={handleMicToggle}
            className={`relative group p-1.5 rounded-full cursor-pointer transition-all duration-300 ${
              isMicActive
                ? 'shadow-[0_0_35px_rgba(52,211,153,0.8),0_10px_25px_rgba(0,0,0,0.8)] border border-emerald-400/80 animate-pulse'
                : 'shadow-[0_0_25px_rgba(244,63,94,0.4),0_10px_25px_rgba(0,0,0,0.8)] border border-red-500/40 hover:border-red-400/70'
            } bg-gradient-to-b from-slate-800 via-slate-900 to-slate-950`}
            title={isMicActive ? 'Click to Mute Neural Mic' : 'Click to Initiate Neural Mic'}
          >
            {/* Bezel Ring with Etched Rim Text */}
            <div className="relative p-3 rounded-full bg-gradient-to-b from-slate-900 via-slate-950 to-slate-900 border border-slate-700/50 flex items-center justify-center">
              {/* Etched Rim Badge */}
              <span className="absolute -top-2.5 text-[8px] font-mono tracking-widest text-cyan-400/80 uppercase px-2 bg-slate-950/95 rounded-full border border-cyan-500/30 font-bold shadow-md">
                NEURAL MIC PROTOCOL
              </span>

              {/* Inner Metallic 3D Button Core */}
              <div
                className={`w-14 h-14 rounded-full flex items-center justify-center transition-all duration-300 border ${
                  isMicActive
                    ? 'bg-gradient-to-br from-emerald-500 via-emerald-950 to-slate-950 border-emerald-400 shadow-[inset_0_2px_12px_rgba(52,211,153,0.8)] animate-pulse'
                    : 'bg-gradient-to-br from-rose-950 via-slate-950 to-slate-900 border-red-500/50 shadow-[inset_0_2px_10px_rgba(244,63,94,0.5)]'
                }`}
              >
                {/* Central Microphone Grid Icon */}
                <svg
                  className={`w-6 h-6 transition-all duration-300 ${
                    isMicActive
                      ? 'text-emerald-300 drop-shadow-[0_0_15px_#34d399] animate-pulse'
                      : 'text-red-500 drop-shadow-[0_0_10px_#f43f5e]'
                  }`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
                  />
                </svg>
              </div>
            </div>
          </motion.button>

          {/* Status Text Block */}
          <div className="flex items-center gap-1.5 font-mono text-[11px] tracking-wider uppercase bg-slate-950/80 px-4 py-1.5 rounded-full border border-cyan-500/30 shadow-[0_0_15px_rgba(0,0,0,0.5)] backdrop-blur-md">
            <span
              className={`font-bold transition-all duration-300 ${
                isMicActive
                  ? 'text-emerald-400 drop-shadow-[0_0_10px_#34d399] animate-pulse'
                  : 'text-red-500 drop-shadow-[0_0_8px_#f43f5e]'
              }`}
            >
              MIC STATUS: {isMicListening ? 'LISTENING...' : isMicActive ? 'ON' : 'OFF'}
            </span>
            <span className="text-slate-600 font-bold">-</span>
            <span
              className={`transition-all duration-300 tracking-widest ${
                isMicActive
                  ? 'text-emerald-300 drop-shadow-[0_0_8px_#34d399] font-bold'
                  : 'text-cyan-400/80 font-medium'
              }`}
            >
              {isMicListening ? 'SPEECH ACTIVE' : isMicActive ? 'MIC ON' : 'CLICK TO INITIATE'}
            </span>
          </div>
        </div>
      )}
    </div>
  );
};

export default AvatarStage;

