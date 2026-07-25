import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import ApiKeyField from './ApiKeyField';

/**
 * TtsKeysAccordion Component
 * Collapsible panel for secondary TTS / Voice synthesis configuration.
 */
export const TtsKeysAccordion = ({
  elevenLabsKey,
  onElevenLabsKeyChange,
  voiceId,
  onVoiceIdChange,
  localTtsEndpoint,
  onLocalTtsEndpointChange,
  className = '',
}) => {
  const [isOpen, setIsOpen] = useState(false);

  const configuredCount = [elevenLabsKey, voiceId, localTtsEndpoint].filter(Boolean).length;

  return (
    <div className={`rounded-xl border border-cyan-500/40 bg-slate-950 overflow-hidden transition-colors ${className}`}>
      {/* Accordion Header Toggle Button */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-4 py-3 flex items-center justify-between text-left cursor-pointer hover:bg-cyan-500/10 transition-colors"
      >
        <div className="flex items-center gap-2 font-mono text-xs font-bold text-cyan-300">
          <span className="w-2 h-2 rounded-full bg-cyan-400 shadow-[0_0_6px_#22d3ee]" />
          <span>VOICE & TTS ENGINE VAULT</span>
          {configuredCount > 0 && (
            <span className="text-[10px] px-2 py-0.5 rounded bg-cyan-950 border border-cyan-400 text-cyan-300 font-bold">
              {configuredCount} ACTIVE
            </span>
          )}
        </div>

        <div className="flex items-center gap-2 text-cyan-400 font-mono font-bold">
          <span className="text-[10px] tracking-wider uppercase">
            {isOpen ? 'COLLAPSE' : 'EXPAND'}
          </span>
          <motion.svg
            animate={{ rotate: isOpen ? 180 : 0 }}
            transition={{ duration: 0.2 }}
            className="w-4 h-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </motion.svg>
        </div>
      </button>

      {/* Accordion Body Content */}
      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className="p-4 pt-2 border-t border-cyan-500/20 flex flex-col gap-3">
              <ApiKeyField
                id="elevenLabsKey"
                label="ElevenLabs API Key (Optional)"
                placeholder="sk_..."
                value={elevenLabsKey}
                onChange={onElevenLabsKeyChange}
                status="OPTIONAL"
              />

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="voiceId" className="text-xs font-mono text-cyan-300 font-bold tracking-wider">
                    Voice ID
                  </label>
                  <input
                    id="voiceId"
                    type="text"
                    value={voiceId}
                    onChange={onVoiceIdChange}
                    placeholder="21m00Tcm4TlvDq8ikWAM"
                    className="w-full px-4 py-2.5 bg-slate-950 border border-cyan-500/40 rounded-xl font-mono text-xs text-white placeholder-cyan-600 focus:border-cyan-400 focus:shadow-[0_0_15px_rgba(34,211,238,0.25)] outline-none"
                  />
                </div>

                <div className="flex flex-col gap-1.5">
                  <label htmlFor="localTts" className="text-xs font-mono text-cyan-300 font-bold tracking-wider">
                    Local TTS Endpoint
                  </label>
                  <input
                    id="localTts"
                    type="text"
                    value={localTtsEndpoint}
                    onChange={onLocalTtsEndpointChange}
                    placeholder="http://localhost:8000/v1/tts"
                    className="w-full px-4 py-2.5 bg-slate-950 border border-cyan-500/40 rounded-xl font-mono text-xs text-white placeholder-cyan-600 focus:border-cyan-400 focus:shadow-[0_0_15px_rgba(34,211,238,0.25)] outline-none"
                  />
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default TtsKeysAccordion;
