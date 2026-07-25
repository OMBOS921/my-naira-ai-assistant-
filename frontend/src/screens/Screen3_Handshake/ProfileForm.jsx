import React, { useState } from 'react';
import { useNairaStore } from '../../state/useNairaStore';
import FloatingPanel from '../../ui3d/FloatingPanel';

export default function ProfileForm({ onConfirm, className = '' }) {
  const storeName = useNairaStore((state) => state.userName);
  const storeRole = useNairaStore((state) => state.userRole);
  const setUserProfile = useNairaStore((state) => state.setUserProfile);

  const [name, setName] = useState(storeName || 'Boss');
  const [role, setRole] = useState(storeRole || 'Lead Architect');

  const handleDirectClick = () => {
    setUserProfile({ name, role, userName: name, userRole: role });
    if (onConfirm) {
      onConfirm();
    } else {
      console.error("onConfirm prop is missing in ProfileForm!");
    }
  };

  return (
    <FloatingPanel depth={40} maxTilt={10} className={`p-6 border-cyan-400/30 ${className}`}>
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <label className="text-[11px] font-mono text-cyan-400/80 uppercase tracking-wider">Operator Name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full px-4 py-2 bg-slate-950/60 border border-cyan-500/20 rounded-xl font-mono text-xs text-cyan-100 outline-none"
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="text-[11px] font-mono text-cyan-400/80 uppercase tracking-wider">System Role</label>
          <input
            type="text"
            value={role}
            onChange={(e) => setRole(e.target.value)}
            className="w-full px-4 py-2 bg-slate-950/60 border border-cyan-500/20 rounded-xl font-mono text-xs text-cyan-100 outline-none"
          />
        </div>
        <button
          type="button"
          onClick={handleDirectClick}
          className="mt-2 py-2.5 px-4 rounded-xl font-mono text-xs font-bold tracking-widest uppercase bg-cyan-500/20 border border-cyan-400 text-cyan-200 hover:bg-cyan-400 hover:text-slate-950"
        >
          CONFIRM NEURAL IDENTITY ✓
        </button>
      </div>
    </FloatingPanel>
  );
}
