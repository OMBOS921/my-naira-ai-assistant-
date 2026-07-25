import React from 'react';
import FloatingPanel from '../../../ui3d/FloatingPanel';

/**
 * AgentRail Component
 * Vertical status rail displaying multi-agent orchestrator state and background worker tasks.
 */
export const AgentRail = ({ className = '' }) => {
  const agents = [
    { id: 'coder', name: 'Coder Agent', status: 'ACTIVE', task: 'Optimizing Vite bundle', type: 'core' },
    { id: 'planner', name: 'Planner Agent', status: 'ACTIVE', task: 'Orchestrating Phase 6', type: 'core' },
    { id: 'researcher', name: 'Research Engine', status: 'INACTIVE', task: 'Knowledge graph standby', type: 'search' },
    { id: 'task', name: 'Autonomous Tasker', status: 'ACTIVE', task: 'Background cron heartbeat', type: 'system' },
    { id: 'vision', name: 'Vision Engine', status: 'INACTIVE', task: '3D Spatial scan standby', type: 'sensor' },
  ];

  return (
    <FloatingPanel depth={30} maxTilt={8} className={`p-4 flex flex-col gap-3 w-64 border-cyan-400/20 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between border-b border-cyan-500/20 pb-2">
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
          <h3 className="font-mono text-xs font-bold text-cyan-300 tracking-wider uppercase">
            MULTI-AGENT RAIL
          </h3>
        </div>
        <span className="text-[10px] font-mono text-cyan-400 font-semibold">3 ACTIVE</span>
      </div>

      {/* Agents List */}
      <div className="flex flex-col gap-2.5">
        {agents.map((agent) => {
          const isActive = agent.status === 'ACTIVE' || agent.status === 'RUNNING';
          const statusText = isActive ? 'ACTIVE' : 'INACTIVE';

          return (
            <div
              key={agent.id}
              className={`p-3 rounded-xl border transition-all flex items-center justify-between cursor-pointer group ${
                isActive
                  ? 'bg-slate-950/70 border-cyan-500/30 hover:border-cyan-400'
                  : 'bg-slate-950/30 border-slate-800/40 opacity-60 hover:opacity-80'
              }`}
            >
              <div className="flex flex-col justify-center gap-1 min-w-0 pr-2">
                <span className={`font-mono text-xs font-semibold ${isActive ? 'text-cyan-200 group-hover:text-cyan-300' : 'text-slate-400'}`}>
                  {agent.name}
                </span>
                <span className="text-[10px] font-mono text-slate-300 truncate">
                  {agent.task}
                </span>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span
                  className={`w-2 h-2 rounded-full ${
                    isActive
                      ? 'bg-emerald-400 shadow-[0_0_8px_#34d399] animate-pulse'
                      : 'bg-slate-600'
                  }`}
                />
                <span
                  className={`text-[9px] font-mono font-bold tracking-wider ${
                    isActive ? 'text-emerald-400' : 'text-slate-500'
                  }`}
                >
                  {statusText}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </FloatingPanel>
  );
};

export default AgentRail;
