import React, { useRef } from 'react';
import { motion, useMotionValue, useTransform, useSpring } from 'framer-motion';

/**
 * FloatingPanel Component
 * Wraps children with 3D physical hover-tilt, continuous floating bobbing animation,
 * glassmorphism background, and dual-layered holographic shadows.
 */
export const FloatingPanel = ({
  children,
  className = '',
  depth = 30,
  maxTilt = 15,
  floatDistance = 8,
  floatDuration = 4,
  style = {},
  ...props
}) => {
  const panelRef = useRef(null);

  // Mouse relative coordinates
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);

  // Transform raw mouse offsets into smooth 3D tilt rotations
  const rawRotateX = useTransform(mouseY, [-150, 150], [maxTilt, -maxTilt]);
  const rawRotateY = useTransform(mouseX, [-150, 150], [-maxTilt, maxTilt]);

  // Spring physics configuration for realistic dampening
  const springConfig = { stiffness: 300, damping: 25 };
  const rotateX = useSpring(rawRotateX, springConfig);
  const rotateY = useSpring(rawRotateY, springConfig);

  const handleMouseMove = (e) => {
    if (!panelRef.current) return;
    const rect = panelRef.current.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;
    mouseX.set(e.clientX - centerX);
    mouseY.set(e.clientY - centerY);
  };

  const handleMouseLeave = () => {
    mouseX.set(0);
    mouseY.set(0);
  };

  return (
    <motion.div
      ref={panelRef}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      animate={{
        y: [0, -floatDistance, 0],
      }}
      transition={{
        y: {
          duration: floatDuration,
          repeat: Infinity,
          ease: 'easeInOut',
        },
      }}
      style={{
        transformStyle: 'preserve-3d',
        rotateX,
        rotateY,
        z: depth,
        ...style,
      }}
      className={`relative rounded-2xl bg-[#0D1230]/95 border border-cyan-400/30 shadow-[0_15px_35px_-5px_rgba(0,0,0,0.8),0_0_30px_rgba(34,211,238,0.2)] transition-all duration-300 hover:border-cyan-400/60 hover:shadow-[0_20px_40px_-5px_rgba(0,0,0,0.9),0_0_40px_rgba(34,211,238,0.3)] ${className}`}
      {...props}
    >
      {/* Inner layer popped out in Z-space */}
      <div className="w-full h-full flex flex-col" style={{ transform: `translateZ(${depth}px)`, transformStyle: 'preserve-3d' }}>
        {children}
      </div>
    </motion.div>
  );
};

export default FloatingPanel;
