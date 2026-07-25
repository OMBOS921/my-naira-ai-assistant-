import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import AvatarStage from '../../avatar/AvatarStage';
import FloatingPanel from '../../ui3d/FloatingPanel';
import ApiKeyField from './ApiKeyField';
import { verifyGeminiKey, verifyOpenCodeZenKey, autoSaveVerifiedKeys, getStoredKey, OPENCODE_ZEN_GET_LINK } from '../../utils/apiVerification';

/**
 * ApiVaultScreen Component (Screen 2)
 * Compact & sleek screen orchestrator for API Key input & validation with persistent localStorage auto-save and instant screen transition.
 */
export const ApiVaultScreen = ({ onProceed }) => {
  const [geminiKey, setGeminiKey] = useState('');
  const [opencodeZenKey, setOpencodeZenKey] = useState('');

  const [isVerifying, setIsVerifying] = useState(false);
  const [validationMessage, setValidationMessage] = useState(null);

  // Pre-fill input fields if keys are already present in localStorage / env
  useEffect(() => {
    const stored = getStoredKey();
    if (stored.geminiKey) setGeminiKey(stored.geminiKey);
    if (stored.opencodeZenKey) setOpencodeZenKey(stored.opencodeZenKey);
  }, []);

  const handleVerifyAndProceed = async (e) => {
    e.preventDefault();
    if (!geminiKey.trim() && !opencodeZenKey.trim()) {
      setValidationMessage({
        type: 'error',
        text: 'API Key Required: Please provide either a Gemini API Key or an OpenCode Zen API Key to proceed.',
      });
      return;
    }

    setIsVerifying(true);
    setValidationMessage({ type: 'info', text: 'Connecting to provider endpoints (Google AI Studio / OpenCode Zen)...' });

    const isGeminiOk = geminiKey.trim() ? await verifyGeminiKey(geminiKey) : false;
    const isZenOk = opencodeZenKey.trim() ? await verifyOpenCodeZenKey(opencodeZenKey) : false;

    if (isGeminiOk || isZenOk) {
      // Auto-Save: Store immediately into localStorage & backend sync
      autoSaveVerifiedKeys({ geminiKey, opencodeZenKey });

      setIsVerifying(false);
      setValidationMessage({
        type: 'success',
        text: `KEYS VERIFIED & SAVED TO LOCALSTORAGE + .ENV! Proceeding to Neural Core...`,
      });

      // Invoke router state setter immediately to switch screens without requiring a reload
      if (onProceed) {
        onProceed();
      }
    } else {
      setIsVerifying(false);
      setValidationMessage({
        type: 'error',
        text: 'Endpoint Verification Failed: Provided key(s) could not be authenticated by Google AI Studio / OpenCode Zen endpoints.',
      });
    }
  };

  return (
    <div className="perspective-stage w-screen h-screen relative flex flex-col items-center justify-between p-6 overflow-y-auto bg-[#0A0E27] text-white select-none">
      {/* Background Cyber Grid */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#1f293715_1px,transparent_1px),linear-gradient(to_bottom,#1f293715_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_50%,#000_70%,transparent_100%)] pointer-events-none" />

      {/* Sleek & Thinner Top Header Bar */}
      <header className="z-30 w-full max-w-6xl flex justify-between items-center border-b border-cyan-500/30 pb-2.5 pt-1 shrink-0 bg-[#0A0E27]">
        <div className="flex items-center gap-3">
          <div className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse shadow-[0_0_10px_#22d3ee]" />
          <h1 className="text-base font-bold font-mono tracking-widest text-cyan-300">
            NAIRA-OS
          </h1>
          <span className="text-xs font-mono text-cyan-400 font-semibold uppercase tracking-wider hidden sm:inline-block border-l border-cyan-500/30 pl-3">
            AUTHENTICATION & API CREDENTIALS
          </span>
        </div>

        <div className="text-xs font-mono text-cyan-300 font-bold tracking-widest uppercase flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_8px_#34d399]" />
          VAULT_STATUS: UNLOCKED
        </div>
      </header>

      {/* Main Grid Layout: Avatar on Left, Compact Credential Vault on Right */}
      <main className="z-10 w-full max-w-5xl flex-1 flex flex-col md:flex-row items-center justify-center gap-6 my-auto py-4 preserve-3d">
        {/* Left Side: Cognitive Avatar Stage Box */}
        <FloatingPanel depth={25} maxTilt={8} className="p-5 flex flex-col items-center justify-center gap-3 bg-[#0D1230] border-cyan-400/40 shrink-0">
          <div className="flex items-center gap-2 border-b border-cyan-500/30 pb-2 w-full justify-center">
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse shadow-[0_0_8px_#22d3ee]" />
            <span className="font-mono text-xs font-bold text-cyan-300 tracking-wider uppercase">
              COGNITIVE AVATAR
            </span>
          </div>
          <AvatarStage size="md" showMic={false} />
          <div className="text-[10px] font-mono text-cyan-300 font-bold uppercase tracking-widest bg-slate-950 px-3 py-1 rounded-full border border-cyan-500/40">
            STATUS: READY FOR KEYS
          </div>
        </FloatingPanel>

        {/* Right Side: Sleek & Compact System Credential Vault Floating Panel */}
        <div className="flex-1 w-full max-w-lg preserve-3d">
          <FloatingPanel depth={30} maxTilt={6} className="p-6 border-cyan-400/40 bg-[#0D1230] shadow-[0_0_40px_rgba(0,0,0,0.8)]">
            <form onSubmit={handleVerifyAndProceed} className="flex flex-col gap-4">
              {/* Form Title */}
              <div className="flex flex-col gap-1 border-b border-cyan-500/30 pb-3">
                <h2 className="text-base font-mono font-bold text-white tracking-wider flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-cyan-400 shadow-[0_0_8px_#22d3ee]" />
                  SYSTEM CREDENTIAL VAULT
                </h2>
                <p className="text-[11px] text-white font-medium leading-relaxed">
                  Provide at least one key (Gemini or OpenCode Zen) to initialize Naira's cognitive engines.
                </p>
              </div>

              {/* Primary Gemini API Key Field */}
              <ApiKeyField
                id="geminiKey"
                label="Gemini API Key (Primary LLM)"
                placeholder="AIzaSy..."
                value={geminiKey}
                onChange={(e) => setGeminiKey(e.target.value)}
                required={false}
                status="REQUIRED OR ZEN"
                helpLink="https://aistudio.google.com/"
                helpLinkText="GET GEMINI KEY"
                helperText="Powers Gemini 2.5/3.0 models."
              />

              {/* OpenCode Zen API Key Field (Points to opencode.ai/zen) */}
              <ApiKeyField
                id="opencodeZenKey"
                label="OpenCode Zen API Key (Optional)"
                placeholder="zen-..."
                value={opencodeZenKey}
                onChange={(e) => setOpencodeZenKey(e.target.value)}
                status="OPTIONAL"
                helpLink={OPENCODE_ZEN_GET_LINK}
                helpLinkText="GET ZEN KEY"
                helperText="Routes via free deepseek-v4-flash endpoint."
              />

              {/* Validation Message Notification */}
              {validationMessage && (
                <motion.div
                  initial={{ opacity: 0, y: -5 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={`p-3 rounded-xl border font-mono text-xs font-semibold flex items-center gap-2 ${
                    validationMessage.type === 'error'
                      ? 'bg-rose-950 border-rose-500 text-white'
                      : validationMessage.type === 'success'
                      ? 'bg-emerald-950 border-emerald-500 text-white'
                      : 'bg-cyan-950 border-cyan-500 text-white'
                  }`}
                >
                  <span className="w-2 h-2 rounded-full bg-current animate-pulse shrink-0" />
                  <span>{validationMessage.text}</span>
                </motion.div>
              )}

              {/* Sleek VERIFY & PROCEED Action Button */}
              <button
                type="submit"
                disabled={isVerifying}
                className="w-full py-3.5 px-6 rounded-xl font-mono text-xs tracking-widest font-bold uppercase transition-all duration-300 cursor-pointer bg-gradient-to-r from-cyan-500 via-cyan-400 to-emerald-400 text-slate-950 shadow-[0_0_20px_rgba(34,211,238,0.4)] hover:shadow-[0_0_30px_rgba(34,211,238,0.6)] hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {isVerifying ? (
                  <>
                    <span className="w-4 h-4 rounded-full border-2 border-slate-950 border-t-transparent animate-spin" />
                    VERIFYING ENDPOINTS...
                  </>
                ) : (
                  <>
                    VERIFY & PROCEED
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                    </svg>
                  </>
                )}
              </button>
            </form>
          </FloatingPanel>
        </div>
      </main>
    </div>
  );
};

export default ApiVaultScreen;
