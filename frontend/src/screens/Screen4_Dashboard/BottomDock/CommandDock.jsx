import React, { useState, useEffect, useRef } from 'react';
import { useNairaStore } from '../../../state/useNairaStore';
import FloatingPanel from '../../../ui3d/FloatingPanel';
import { useNairaSocket } from '../../../hooks/useNairaSocket';

/**
 * Helper to speak text out loud using browser Web Speech API (speechSynthesis).
 * Attempts to pick an English female voice for Naira's AI persona.
 */
const speakNairaText = (text, onStart, onEnd) => {
  if (!('speechSynthesis' in window)) {
    console.warn('[WebSpeech] SpeechSynthesis is not supported in this browser.');
    if (onStart) onStart();
    setTimeout(() => {
      if (onEnd) onEnd();
    }, 2500);
    return;
  }

  // Cancel any currently playing speech to avoid overlap
  window.speechSynthesis.cancel();

  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 1.0;
  utterance.pitch = 1.05;

  const voices = window.speechSynthesis.getVoices();

  // Filter for English female or natural voice for AI feel
  const femaleVoice =
    voices.find(
      (v) =>
        v.lang.startsWith('en') &&
        (v.name.includes('Female') ||
          v.name.includes('Google UK English Female') ||
          v.name.includes('Microsoft Zira') ||
          v.name.includes('Samantha') ||
          v.name.includes('Victoria') ||
          v.name.includes('Karen') ||
          v.name.includes('Natural'))
    ) ||
    voices.find((v) => v.lang.startsWith('en') && !v.name.toLowerCase().includes('male')) ||
    voices.find((v) => v.lang.startsWith('en')) ||
    voices[0];

  if (femaleVoice) {
    utterance.voice = femaleVoice;
  }

  utterance.onstart = () => {
    if (onStart) onStart();
  };

  utterance.onend = () => {
    if (onEnd) onEnd();
  };

  utterance.onerror = (err) => {
    console.error('[WebSpeech] Speech synthesis error:', err);
    if (onEnd) onEnd();
  };

  window.speechSynthesis.speak(utterance);
};

/**
 * CommandDock Component
 * Right-hand Chat & Command Panel featuring live WebSocket message history log,
 * real-time Web Speech API audio output, connection status indicator, and prompt bar.
 */
export const CommandDock = ({ className = '' }) => {
  const setAvatarMode = useNairaStore((state) => state.setAvatarMode);
  const userName = useNairaStore((state) => state.userName);
  const userRole = useNairaStore((state) => state.userRole);
  const spokenText = useNairaStore((state) => state.spokenText);
  const setSpokenText = useNairaStore((state) => state.setSpokenText);

  const [prompt, setPrompt] = useState('');
  const [messages, setMessages] = useState([
    { sender: 'Naira', text: 'Neural links verified. Waiting for operator instructions...', type: 'system' },
  ]);

  const { connectionState, isConnected, sendMessage, lastMessage } = useNairaSocket('ws://localhost:8000/ws/naira');
  const chatBottomRef = useRef(null);

  // Immediately send hidden system_init payload to sync user identity when WebSocket connects
  useEffect(() => {
    if (isConnected) {
      sendMessage({
        type: 'system_init',
        name: userName,
        role: userRole,
      });
    }
  }, [isConnected, userName, userRole, sendMessage]);

  // Auto-dispatch spoken text captured by Neural Ears (Web Speech API)
  useEffect(() => {
    if (spokenText && spokenText.trim()) {
      const speechMsg = spokenText.trim();
      setSpokenText('');

      setMessages((prev) => [...prev, { sender: 'Operator', text: speechMsg, type: 'user' }]);
      setAvatarMode('thinking');

      const sentSuccessfully = sendMessage(speechMsg);
      if (!sentSuccessfully) {
        setTimeout(() => {
          setMessages((prev) => [
            ...prev,
            { sender: 'System', text: 'Notice: Socket re-connecting. Message queued/offline.', type: 'system' },
          ]);
          setAvatarMode('idle');
        }, 500);
      }
    }
  }, [spokenText, sendMessage, setSpokenText, setAvatarMode]);

  // Pre-fetch voices when component mounts
  useEffect(() => {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.getVoices();
      const handleVoicesChanged = () => {
        window.speechSynthesis.getVoices();
      };
      window.speechSynthesis.addEventListener('voiceschanged', handleVoicesChanged);
      return () => {
        window.speechSynthesis.removeEventListener('voiceschanged', handleVoicesChanged);
      };
    }
  }, []);

  // Handle incoming WebSocket messages from backend & speak using Web Speech API
  useEffect(() => {
    if (!lastMessage) return;

    const senderName = lastMessage.sender === 'naira' ? 'Naira' : lastMessage.sender || 'Naira';
    const messageText = lastMessage.text || lastMessage.content || '';

    if (messageText) {
      setMessages((prev) => [
        ...prev,
        { sender: senderName, text: messageText, type: 'naira' },
      ]);

      // Trigger Web Speech audio output and synchronize avatarMode (speaking -> idle)
      speakNairaText(
        messageText,
        () => setAvatarMode('speaking'),
        () => setAvatarMode('idle')
      );
    }
  }, [lastMessage, setAvatarMode]);

  // Auto-scroll chat log to bottom
  useEffect(() => {
    if (chatBottomRef.current) {
      chatBottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  const quickActions = [
    { label: '⚡ Run Diagnostic', mode: 'thinking', prompt: 'Run complete system diagnostic' },
    { label: '💻 Refactor Code', mode: 'speaking', prompt: 'Refactor current active workspace code' },
    { label: '🧠 Search Memory', mode: 'listening', prompt: 'Search long term vector memory' },
  ];

  const handleSendPrompt = (e) => {
    e.preventDefault();
    if (!prompt.trim()) return;

    const userMsg = prompt.trim();
    setPrompt('');
    setMessages((prev) => [...prev, { sender: 'Operator', text: userMsg, type: 'user' }]);

    setAvatarMode('thinking');

    // Send payload to backend over WebSocket
    const sentSuccessfully = sendMessage(userMsg);
    if (!sentSuccessfully) {
      // Fallback notification if WS is offline/connecting
      setTimeout(() => {
        setMessages((prev) => [
          ...prev,
          { sender: 'System', text: 'Notice: Socket re-connecting. Message queued/offline.', type: 'system' },
        ]);
        setAvatarMode('idle');
      }, 500);
    }
  };

  const handleQuickAction = (action) => {
    setAvatarMode(action.mode);
    setMessages((prev) => [...prev, { sender: 'Operator', text: action.prompt, type: 'user' }]);
    sendMessage(action.prompt);
  };

  return (
    <FloatingPanel depth={40} maxTilt={6} className={`p-4 flex flex-col h-[580px] w-80 md:w-96 border-cyan-400/30 ${className}`}>
      {/* Panel Header with Live WebSocket Status */}
      <div className="flex items-center justify-between border-b border-cyan-500/20 pb-3 shrink-0">
        <div className="flex items-center gap-2">
          <span
            className={`w-2 h-2 rounded-full animate-pulse ${
              isConnected
                ? 'bg-emerald-400 shadow-[0_0_8px_#34d399]'
                : connectionState === 'connecting'
                ? 'bg-amber-400 shadow-[0_0_8px_#fbbf24]'
                : 'bg-rose-500 shadow-[0_0_8px_#f43f5e]'
            }`}
          />
          <h3 className="font-mono text-xs font-bold text-cyan-200 tracking-wider uppercase">
            CHAT & COMMAND DOCK
          </h3>
        </div>
        <div className="font-mono text-[10px] uppercase font-semibold px-2 py-0.5 rounded border border-cyan-500/20 text-cyan-400 bg-slate-900/60">
          {connectionState}
        </div>
      </div>

      {/* Message Feed Container (Takes remaining vertical space & scrollable) */}
      <div className="flex-1 overflow-y-auto my-3 p-2 flex flex-col gap-2.5 bg-slate-950/50 rounded-xl border border-cyan-500/10 font-mono text-xs scrollbar-thin">
        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`p-2 rounded-lg leading-relaxed ${
              msg.sender === 'Operator'
                ? 'bg-cyan-950/60 border border-cyan-500/30 text-cyan-100 self-end max-w-[85%]'
                : msg.sender === 'Naira'
                ? 'bg-slate-900/80 border border-emerald-500/30 text-white self-start max-w-[90%]'
                : 'bg-slate-900/40 text-slate-300 text-[11px]'
            }`}
          >
            <div className="text-[9px] text-cyan-400 font-bold uppercase tracking-wider mb-0.5">
              {msg.sender}
            </div>
            <p className="text-[11px] leading-relaxed">{msg.text}</p>
          </div>
        ))}
        <div ref={chatBottomRef} />
      </div>

      {/* Input Section (Anchored to bottom) */}
      <div className="mt-auto flex flex-col gap-2.5 shrink-0">
        {/* Quick Action Chips */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-none">
          {quickActions.map((action, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => handleQuickAction(action)}
              className="px-2.5 py-1 rounded-lg bg-slate-950/70 border border-cyan-500/30 text-[10px] font-mono text-cyan-300 hover:border-cyan-400 hover:bg-cyan-500/20 transition-all cursor-pointer shrink-0 font-medium"
            >
              {action.label}
            </button>
          ))}
        </div>

        {/* Command Input Bar */}
        <form onSubmit={handleSendPrompt} className="flex items-center gap-2 pt-2 border-t border-cyan-500/20">
          <input
            type="text"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Command Naira-OS..."
            className="flex-1 px-3 py-2 bg-slate-950/80 border border-cyan-500/30 rounded-xl font-mono text-xs text-white placeholder-cyan-700/60 outline-none transition-all focus:border-cyan-400 focus:shadow-[0_0_15px_rgba(34,211,238,0.25)]"
          />

          <button
            type="submit"
            className="py-2 px-3.5 rounded-xl font-mono text-xs font-bold tracking-wider uppercase transition-all duration-300 cursor-pointer bg-gradient-to-r from-cyan-500 to-emerald-400 text-slate-950 hover:shadow-[0_0_15px_rgba(34,211,238,0.4)] hover:scale-105 active:scale-95 flex items-center justify-center shrink-0"
          >
            SEND
          </button>
        </form>
      </div>
    </FloatingPanel>
  );
};

export default CommandDock;
