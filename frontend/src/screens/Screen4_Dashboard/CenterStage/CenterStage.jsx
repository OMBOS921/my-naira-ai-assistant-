import React from 'react';
import AvatarStage from '../../../avatar/AvatarStage';

/**
 * CenterStage Component
 * Dominant central dashboard stage hosting the perfectly concentric avatar circle assembly,
 * ticking data ring, holographic HUD overlays, and central Neural Mic protocol panel.
 */
export const CenterStage = ({ className = '' }) => {
  return (
    <div className={`relative flex items-center justify-center preserve-3d -translate-y-4 ${className}`}>
      {/* Main Concentric Avatar & Ring Stage */}
      <AvatarStage size="lg" showMic={true} className="z-10" />
    </div>
  );
};

export default CenterStage;

