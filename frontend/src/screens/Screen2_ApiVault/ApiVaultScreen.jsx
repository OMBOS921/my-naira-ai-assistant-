import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import AvatarStage from '../../avatar/AvatarStage';
import ApiKeyField from './ApiKeyField';
import { getVaultStatus, saveVaultConfiguration, OPENCODE_ZEN_GET_LINK } from '../../utils/apiVerification';

export const ApiVaultScreen = ({ onProceed }) => {
  const [geminiKey, setGeminiKey] = useState('');
  const [opencodeZenKey, setOpencodeZenKey] = useState('');

  const [isVerifying, setIsVerifying] = useState(false);
  const [validationMessage, setValidationMessage] = useState(null);

  useEffect(() => {
    getVaultStatus().then((status) => {
      if (status && status.configured) {
        localStorage.setItem('naira_setup_complete', 'true');
        if (onProceed) onProceed();
      }
    }).catch(() => { });
  }, []);

  const handleVerifyAndProceed = async (e) => {
    if (e) e.preventDefault();
    console.log("🔴 [VAULT] VERIFY BUTTON CLICKED!");

    if (!geminiKey.trim() && !opencodeZenKey.trim()) {
      setValidationMessage({
        type: 'error',
        text: 'API Key Required: Please provide either a Gemini or OpenCode Zen API Key.',
      });
      return;
    }

    setIsVerifying(true);
    setValidationMessage({ type: 'info', text: 'Verifying with the secure local vault...' });

    const provider = geminiKey.trim() ? 'gemini' : 'deepseek';
    const apiKey = geminiKey.trim() || opencodeZenKey.trim();

    try {
      const res = await saveVaultConfiguration({ provider, apiKey });
      console.log("🔴 [VAULT] BACKEND SUCCESS:", res);
      localStorage.setItem('naira_setup_complete', 'true');
      setIsVerifying(false);
      setValidationMessage({
        type: 'success',
        text: 'KEY VERIFIED & SAVED! Proceeding...',
      });
      if (onProceed) onProceed();
    } catch (error) {
      console.error("🔴 [VAULT] BACKEND REJECTED/FAILED:", error);
      setIsVerifying(false);
      setValidationMessage({
        type: 'error',
        text: error.message || 'Endpoint verification failed.',
      });
    }
  };

  return (
    <div className="w-screen h-screen relative flex flex-col items-center justify-between p-6 overflow-y-auto bg-[#0A0E27] text-white select-none">
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#1f293715_1px,transparent_1px),linear-gradient(to_bottom,#1f293715_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_50%,#000_70%,transparent_100%)] pointer-events-none" />

      <header className="z-30 w-full max-w-6xl flex justify-between items-center border-b border-cyan-500/30 pb-2.5 pt-1 shrink-0 bg-[#0A0E27]">
        <div className="flex items-center gap-3">
          <div className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse shadow-[0_0_10px_#22d3ee]" />
          <h1 className="text-base font-bold font-mono tracking-widest text-cyan-300">
            NAIRA-OS
          </h1>
        </div>
        <div className="text-xs font-mono text-cyan-300 font-bold tracking-widest uppercase flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_8px_#34d399]" />
          VAULT_STATUS: UNLOCKED
        </div>
      </header>

      <main className="z-10 w-full max-w-5xl flex-1 flex flex-col md:flex-row items-center justify-center gap-6 my-auto py-4">

        {/* Left Side: Avatar */}
        <div className="p-5 flex flex-col items-center justify-center gap-3 bg-[#0D1230] border border-cyan-400/40 rounded-2xl shrink-0">
          <AvatarStage size="md" showMic={false} />
          <div className="text-[10px] font-mono text-cyan-300 font-bold uppercase tracking-widest bg-slate-950 px-3 py-1 rounded-full border border-cyan-500/40">
            STATUS: READY FOR KEYS
          </div>
        </div>

        {/* Right Side: Static Div instead of 3D Panel */}
        <div className="flex-1 w-full max-w-lg">
          <div className="p-6 border border-cyan-400/40 bg-[#0D1230] shadow-[0_0_40px_rgba(0,0,0,0.8)] rounded-2xl">
            <form className="flex flex-col gap-4">
              <div className="flex flex-col gap-1 border-b border-cyan-500/30 pb-3">
                <h2 className="text-base font-mono font-bold text-white tracking-wider flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-cyan-400 shadow-[0_0_8px_#22d3ee]" />
                  SYSTEM CREDENTIAL VAULT
                </h2>
              </div>

              <ApiKeyField
                id="geminiKey"
                label="Gemini API Key"
                placeholder="AIzaSy..."
                value={geminiKey}
                onChange={(e) => setGeminiKey(e.target.value)}
                required={false}
                status="REQUIRED OR ZEN"
                helpLink="https://aistudio.google.com/"
                helpLinkText="GET GEMINI KEY"
                helperText="Powers Gemini 2.5/3.0 models."
              />

              <ApiKeyField
                id="opencodeZenKey"
                label="OpenCode Zen API Key"
                placeholder="zen-..."
                value={opencodeZenKey}
                onChange={(e) => setOpencodeZenKey(e.target.value)}
                status="OPTIONAL"
                helpLink={OPENCODE_ZEN_GET_LINK}
                helpLinkText="GET ZEN KEY"
                helperText="Routes via free deepseek-v4-flash endpoint."
              />

              {validationMessage && (
                <div className={`p-3 rounded-xl border font-mono text-xs font-semibold flex items-center gap-2 ${validationMessage.type === 'error' ? 'bg-rose-950 border-rose-500 text-white' : 'bg-cyan-950 border-cyan-500 text-white'
                  }`}>
                  <span className="w-2 h-2 rounded-full bg-current animate-pulse shrink-0" />
                  <span>{validationMessage.text}</span>
                </div>
              )}

              <button
                type="button"
                onClick={handleVerifyAndProceed}
                disabled={isVerifying}
                className="w-full py-3.5 px-6 rounded-xl font-mono text-xs tracking-widest font-bold uppercase transition-all duration-300 cursor-pointer bg-gradient-to-r from-cyan-500 via-cyan-400 to-emerald-400 text-slate-950 shadow-[0_0_20px_rgba(34,211,238,0.4)] hover:opacity-90 disabled:opacity-50 flex items-center justify-center gap-2 relative z-50"
              >
                {isVerifying ? "VERIFYING ENDPOINTS..." : "VERIFY & PROCEED"}
              </button>
            </form>
          </div>
        </div>
      </main>
    </div>
  );
};

export default ApiVaultScreen;