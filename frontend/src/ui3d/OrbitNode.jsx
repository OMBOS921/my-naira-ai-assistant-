import React from 'react';
import { motion } from 'framer-motion';

/**
 * OrbitNode Component
 * Renders a glowing background task/engine node positioned around an orbital trajectory.
 * Calculates absolute offset using trigonometry and animates floating height.
 */
export const OrbitNode = ({
  angle = 0, // Angle in degrees (e.g. 0 to 360)
  radius = 150, // Orbital radius in pixels
  label = 'Task Engine',
  status = 'ok', // 'ok' | 'pending'
  className = '',
  style = {},
  ...props
}) => {
  // Convert angle in degrees to radians
  const radians = (angle * Math.PI) / 180;

  // Calculate orbital X and Y coordinates
  const posX = Math.cos(radians) * radius;
  const posY = Math.sin(radians) * radius;

  const isOk = status === 'ok';

  return (
    <motion.div
      initial={{ x: posX, y: posY, opacity: 0, scale: 0.8 }}
      animate={{
        x: posX,
        y: [posY - 4, posY, posY - 4],
        opacity: 1,
        scale: 1,
      }}
      transition={{
        y: {
          duration: 3,
          repeat: Infinity,
          ease: 'easeInOut',
        },
        opacity: { duration: 0.5 },
      }}
      style={{
        position: 'absolute',
        transformStyle: 'preserve-3d',
        ...style,
      }}
      className={`group flex items-center gap-2 cursor-pointer ${className}`}
      {...props}
    >
      {/* Node Glowing Circle */}
      <div className="relative flex items-center justify-center">
        <div
          className={`w-3 h-3 rounded-full transition-all duration-300 ${
            isOk
              ? 'bg-cyan-400 shadow-[0_0_12px_#22d3ee]'
              : 'bg-slate-300/80 shadow-[0_0_8px_rgba(255,255,255,0.4)]'
          }`}
        />
        {/* Subtle Pulse Aura for Active OK status */}
        {isOk && (
          <span className="absolute inset-0 w-3 h-3 rounded-full bg-cyan-400/50 animate-ping" />
        )}
      </div>

      {/* Node Label */}
      {label && (
        <div className="px-2 py-0.5 rounded-md bg-slate-950/60 border border-slate-800/80 backdrop-blur-md shadow-md transition-colors group-hover:border-cyan-500/40">
          <span
            className={`text-[10px] font-mono tracking-wider uppercase whitespace-nowrap ${
              isOk ? 'text-cyan-300' : 'text-slate-400'
            }`}
          >
            {label}
          </span>
        </div>
      )}
    </motion.div>
  );
};

export default OrbitNode;
