import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';

/**
 * GreetingTypewriter Component
 * Smoothly reveals Naira's holographic greeting message character-by-character with a glowing cyber cursor.
 */
export const GreetingTypewriter = ({
  text = 'Initializing neural handshake... Welcome, Boss. I am Naira, your autonomous OS. System protocols are online and ready for your command.',
  speed = 35,
  onComplete,
  className = '',
}) => {
  const [displayedText, setDisplayedText] = useState('');
  const [isComplete, setIsComplete] = useState(false);

  useEffect(() => {
    setDisplayedText('');
    setIsComplete(false);

    let currentIndex = 0;
    const timer = setInterval(() => {
      if (currentIndex < text.length) {
        setDisplayedText((prev) => prev + text.charAt(currentIndex));
        currentIndex++;
      } else {
        clearInterval(timer);
        setIsComplete(true);
        if (onComplete) onComplete();
      }
    }, speed);

    return () => clearInterval(timer);
  }, [text, speed]);

  return (
    <div className={`font-mono text-sm leading-relaxed text-cyan-200 tracking-wide ${className}`}>
      <span>{displayedText}</span>
      <motion.span
        animate={{ opacity: [1, 0, 1] }}
        transition={{ duration: 0.8, repeat: Infinity }}
        className="inline-block w-2 h-4 ml-1 bg-cyan-400 align-middle shadow-[0_0_8px_#22d3ee]"
      />
    </div>
  );
};

export default GreetingTypewriter;
