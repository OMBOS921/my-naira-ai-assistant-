import React from 'react';
import SystemVitalsStrip from './TopBar/SystemVitalsStrip';
import AgentRail from './LeftRail/AgentRail';
import CenterStage from './CenterStage/CenterStage';
import CommandDock from './BottomDock/CommandDock';

/**
 * DashboardScreen Component (Screen 4)
 * Master orchestrator for Screen 4 bringing together TopBar, AgentRail, CenterStage, and Right-Side CommandDock.
 * Uses responsive flexbox layout to dynamically fill the browser viewport.
 */
export const DashboardScreen = () => {
  return (
    <div className="perspective-stage w-full h-full relative flex flex-col justify-between items-center p-4 overflow-hidden bg-[#0A0E27] text-white select-none">
      {/* Background Cyber Grid */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#1f293715_1px,transparent_1px),linear-gradient(to_bottom,#1f293715_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_50%,#000_70%,transparent_100%)] pointer-events-none" />

      {/* TopBar Vitals Strip */}
      <SystemVitalsStrip className="w-full max-w-7xl mx-auto z-20 shrink-0" />

      {/* Main Center Grid Layout */}
      <main className="z-10 w-full max-w-7xl mx-auto flex-1 flex items-center justify-between gap-6 my-2 preserve-3d px-2 min-h-0">
        {/* Left Agent Status Rail */}
        <AgentRail className="z-20 hidden lg:flex shrink-0 h-full max-h-[580px]" />

        {/* Center Holographic Stage */}
        <CenterStage className="z-10 flex-1 min-w-0 h-full" />

        {/* Right Chat / Command Dock Panel */}
        <CommandDock className="z-20 flex shrink-0 h-full max-h-[580px]" />
      </main>
    </div>
  );
};

export default DashboardScreen;
