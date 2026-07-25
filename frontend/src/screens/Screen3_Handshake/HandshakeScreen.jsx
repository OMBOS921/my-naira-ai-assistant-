import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { useNairaStore } from '../../state/useNairaStore';
import AvatarStage from '../../avatar/AvatarStage';
import FloatingPanel from '../../ui3d/FloatingPanel';
import GreetingTypewriter from './GreetingTypewriter';
import ProfileForm from './ProfileForm';

/**
 * HandshakeScreen Component (Screen 3)
 * Orchestrates Naira's interactive neural handshake greeting and user profile confirmation.
 */
export default function HandshakeScreen({ onHandshakeComplete }) {
  const setAvatarMode = useNairaStore((state) => state.setAvatarMode);
  const setHandshakeCompleteStore = useNairaStore((state) => state.setHandshakeComplete);
  const userName = useNairaStore((state) => state.userName);

  const [isHandshakeDone, setIsHandshakeDone] = useState(false);

  useEffect(() => {
    // Set avatar mode to greeting when handshake screen mounts
    setAvatarMode('greeting');
  }, [setAvatarMode]);

  const handleProfileSubmit = () => {
    setIsHandshakeDone(true);
    setHandshakeCompleteStore(true);
    localStorage.setItem('naira_handshake_done', 'true');
    if (onHandshakeComplete) {
      onHandshakeComplete();
    }
  };

  const handleEnterDashboard = () => {
    if (onHandshakeComplete) {
      onHandshakeComplete();
    }
  };

  return (
    <div className="perspective-stage w-full h-full relative flex flex-col justify-between items-center p-6 overflow-hidden bg-[#0A0E27] text-white select-none">
      {/* Background Cyber Grid */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#1f293715_1px,transparent_1px),linear-gradient(to_bottom,#1f293715_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_50%,#000_70%,transparent_100%)] pointer-events-none" />

      {/* Header Overlay */}
      <header className="z-30 w-full max-w-6xl mx-auto flex justify-between items-center border-b border-cyan-500/20 pb-4 shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse shadow-[0_0_10px_#22d3ee]" />
          <h1 className="text-lg font-bold font-mono tracking-widest text-cyan-300">
            NAIRA-OS
          </h1>
        </div>
        <div className="text-xs font-mono text-cyan-300 tracking-widest uppercase flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
          HANDSHAKE_PROTOCOL: IN_PROGRESS
        </div>
      </header>

      {/* Main Handshake Content Layout */}
      <main className="z-10 w-full max-w-6xl mx-auto flex-1 flex flex-col md:flex-row items-center justify-center gap-8 my-4 preserve-3d">
        {/* Left Stage: Prominent Avatar Stage (Mic button disabled for Handshake) */}
        <FloatingPanel depth={50} maxTilt={15} className="p-6 flex items-center justify-center">
          <AvatarStage size="lg" showMic={false} />
        </FloatingPanel>

        {/* Right Panels: Holographic Typewriter Speech & Profile Form */}
        <div className="flex flex-col gap-4 w-full max-w-md preserve-3d">
          {/* Holographic Dialog Bubble Panel */}
          <FloatingPanel depth={35} maxTilt={8} className="p-5 border-cyan-400/30">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-[10px] font-mono tracking-widest text-cyan-400/80 uppercase">
                NAIRA AUDIO TRANSMISSION
              </span>
            </div>
            <GreetingTypewriter
              text={`Neural handshake established. Welcome back, ${userName || 'Boss'}. I am Naira, your autonomous operating system. All core cognitive modules are online and responsive.`}
              speed={30}
            />
          </FloatingPanel>

          {/* User Profile Registration Form */}
          <ProfileForm onConfirm={onHandshakeComplete} />
        </div>
      </main>

      {/* Footer / Transition Button */}
      <footer className="z-30 w-full max-w-xl mx-auto flex flex-col items-center shrink-0">
        {isHandshakeDone ? (
          <motion.button
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            onClick={handleEnterDashboard}
            className="w-full py-4 px-8 rounded-2xl font-mono text-xs tracking-widest font-bold uppercase transition-all duration-300 cursor-pointer bg-gradient-to-r from-cyan-500 via-emerald-400 to-cyan-400 text-slate-950 shadow-[0_0_30px_rgba(34,211,238,0.5)] hover:scale-[1.03] active:scale-[0.98] flex items-center justify-center gap-3"
          >
            ENTER NAIRA-OS DASHBOARD
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M13 7l5 5m0 0l-5 5m5-5H6" />
            </svg>
          </motion.button>
        ) : (
          <div className="text-xs font-mono text-cyan-400/60 tracking-wider flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-ping" />
            PLEASE CONFIRM YOUR IDENTITY TO COMPLETE HANDSHAKE
          </div>
        )}
      </footer>
    </div>
  );
}

export { HandshakeScreen };
