import React from 'react';
import OrbitNode from '../../ui3d/OrbitNode';

/**
 * EngineOrbitRing Component
 * Evenly distributes system engine nodes in a 360-degree orbital circle around the avatar stage.
 */
export const EngineOrbitRing = ({
  engines = [],
  radius = 340,
  className = '',
}) => {
  const count = engines.length || 1;
  const stepAngle = 360 / count;

  return (
    <div className={`absolute inset-0 flex items-center justify-center preserve-3d pointer-events-none ${className}`}>
      {/* Decorative Outer Trajectory Ring */}
      <div
        className="absolute rounded-full border border-cyan-500/10 border-dashed pointer-events-none animate-[spin_60s_linear_infinite]"
        style={{
          width: radius * 2,
          height: radius * 2,
          transformStyle: 'preserve-3d',
        }}
      />

      {/* Distributed Engine Orbit Nodes */}
      {engines.map((engine, index) => {
        const angle = stepAngle * index - 90; // Top starting position (-90deg)
        return (
          <OrbitNode
            key={engine.id || `${engine.name}-${index}`}
            angle={angle}
            radius={radius}
            label={engine.name}
            status={engine.status || 'ok'}
            className="pointer-events-auto"
          />
        );
      })}
    </div>
  );
};

export default EngineOrbitRing;
