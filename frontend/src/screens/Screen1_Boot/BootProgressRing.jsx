import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';

/**
 * BootProgressRing Component
 * Futuristic glowing progress HUD for system boot sequence.
 */
export const BootProgressRing = ({ onBootComplete, className = '' }) => {
  const [progress, setProgress] = useState(0);
  const [statusText, setStatusText] = useState('INITIALIZING SYSTEM...');

  const bootStages = [
    { threshold: 15, text: 'LOADING HARDWARE ABSTRACTION LAYER...' },
    { threshold: 35, text: 'MOUNTING NEURAL MEMORY STORE...' },
    { threshold: 55, text: 'ESTABLISHING AUTONOMOUS ENGINE MATRIX...' },
    { threshold: 75, text: 'VERIFYING VISION & AUDIO STREAMS...' },
    { threshold: 90, text: 'SYNCHRONIZING HOLOGRAPHIC STAGE...' },
    { threshold: 100, text: 'NAIRA-OS CORE READY' },
  ];

  useEffect(() => {
    const interval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 100) {
          clearInterval(interval);
          if (onBootComplete) {
            setTimeout(onBootComplete, 600);
          }
          return 100;
        }
        const next = prev + 1;
        const stage = bootStages.find((s) => next <= s.threshold);
        if (stage && stage.text !== statusText) {
          setStatusText(stage.text);
        }
        return next;
      });
    }, 35);

    return () => clearInterval(interval);
  }, [onBootComplete]);

  // Calculate SVG Circle circumference
  const radius = 24;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (progress / 100) * circumference;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.8, delay: 0.2 }}
      className={`flex items-center gap-4 px-6 py-3 rounded-2xl bg-slate-950/70 backdrop-blur-xl border border-cyan-500/30 shadow-[0_0_30px_rgba(6,182,212,0.2)] ${className}`}
    >
      {/* SVG Arc Progress Ring */}
      <div className="relative w-14 h-14 flex items-center justify-center">
        <svg className="w-full h-full transform -rotate-90">
          {/* Track Circle */}
          <circle
            cx="28"
            cy="28"
            r={radius}
            stroke="currentColor"
            strokeWidth="3"
            className="text-cyan-950/60"
            fill="transparent"
          />
          {/* Animated Glow Circle */}
          <circle
            cx="28"
            cy="28"
            r={radius}
            stroke="currentColor"
            strokeWidth="3.5"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            className="text-cyan-400 transition-all duration-150 ease-out shadow-[0_0_12px_#22d3ee]"
            fill="transparent"
          />
        </svg>

        {/* Center Percentage Display */}
        <span className="absolute font-mono text-[11px] font-bold text-cyan-300">
          {progress}%
        </span>
      </div>

      {/* Progress Tech Text & Horizontal Bar */}
      <div className="flex flex-col gap-1.5 min-w-[260px]">
        <div className="flex justify-between items-center text-xs font-mono tracking-widest text-cyan-300">
          <span className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping" />
            BOOT SEQUENCE
          </span>
          <span className="text-cyan-500/80">{progress === 100 ? 'READY' : 'RUNNING'}</span>
        </div>

        {/* Linear Progress Bar */}
        <div className="w-full h-1.5 rounded-full bg-slate-900 overflow-hidden border border-cyan-500/20">
          <motion.div
            className="h-full bg-gradient-to-r from-cyan-500 to-emerald-400 shadow-[0_0_10px_#22d3ee]"
            style={{ width: `${progress}%` }}
          />
        </div>

        {/* Status Step Detail */}
        <span className="text-[10px] font-mono text-cyan-400/60 tracking-wider truncate uppercase">
          {statusText}
        </span>
      </div>
    </motion.div>
  );
};

export default BootProgressRing;
