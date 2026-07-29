import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
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

  // Handle incoming WebSocket messages from backend & play synthesized audio payload
  useEffect(() => {
    if (!lastMessage) return;

    const msgType = lastMessage.type || 'message';
    const isToolStart = msgType === 'tool_execution_start';
    const isToolResult = msgType === 'tool_execution_result';
    const isToolEvent = isToolStart || isToolResult;

    let senderName = lastMessage.sender === 'naira' ? 'Naira' : lastMessage.sender || 'Naira';
    let messageText = lastMessage.text || lastMessage.content || '';
    let msgCategory = 'naira';

    if (isToolStart) {
      senderName = 'Naira (Tool Execution)';
      msgCategory = 'tool_start';
      if (!messageText) {
        const toolName = lastMessage.tool || 'execute_local_python';
        const scriptCode = lastMessage.script_code || '';
        messageText = `### 🛠️ Executing Tool: \`${toolName}\`\n\`\`\`python\n${scriptCode}\n\`\`\``;
      }
    } else if (isToolResult) {
      senderName = 'Naira (Tool Result)';
      msgCategory = 'tool_result';
      if (!messageText) {
        const output = lastMessage.output || lastMessage.stdout || lastMessage.stderr || '';
        messageText = `### 📤 Execution Output:\n\`\`\`text\n${output}\n\`\`\``;
      }
    }

    if (messageText) {
      setMessages((prev) => [
        ...prev,
        { sender: senderName, text: messageText, type: msgCategory },
      ]);

      // Only synthesize speech for standard conversational messages, not code/log tool events
      if (!isToolEvent) {
        if (lastMessage.audio) {
          try {
            const audio = new Audio(`data:audio/wav;base64,${lastMessage.audio}`);
            setAvatarMode('speaking');
            audio.onended = () => setAvatarMode('idle');
            audio.onerror = () => {
              speakNairaText(
                messageText,
                () => setAvatarMode('speaking'),
                () => setAvatarMode('idle')
              );
            };
            audio.play().catch((err) => {
              console.warn('[Audio] Auto-play failed, falling back to WebSpeech:', err);
              speakNairaText(
                messageText,
                () => setAvatarMode('speaking'),
                () => setAvatarMode('idle')
              );
            });
          } catch (e) {
            speakNairaText(
              messageText,
              () => setAvatarMode('speaking'),
              () => setAvatarMode('idle')
            );
          }
        } else {
          speakNairaText(
            messageText,
            () => setAvatarMode('speaking'),
            () => setAvatarMode('idle')
          );
        }
      } else {
        if (isToolStart) setAvatarMode('thinking');
      }
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
            className={`p-2.5 rounded-lg leading-relaxed ${
              msg.sender === 'Operator'
                ? 'bg-cyan-950/60 border border-cyan-500/30 text-cyan-100 self-end max-w-[85%]'
                : msg.type === 'tool_start'
                ? 'bg-slate-900/90 border border-amber-500/40 text-amber-200 self-start max-w-[95%]'
                : msg.type === 'tool_result'
                ? 'bg-slate-950/90 border border-emerald-500/40 text-emerald-200 self-start max-w-[95%]'
                : msg.sender === 'Naira'
                ? 'bg-slate-900/80 border border-cyan-500/30 text-white self-start max-w-[92%]'
                : 'bg-slate-900/40 text-slate-300 text-[11px]'
            }`}
          >
            <div className="text-[9px] text-cyan-400 font-bold uppercase tracking-wider mb-1">
              {msg.sender}
            </div>
            <div className="text-[11px] leading-relaxed select-text space-y-1">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  table: ({ node, ...props }) => (
                    <div className="overflow-x-auto my-2 rounded border border-cyan-500/30">
                      <table className="min-w-full divide-y divide-cyan-500/30 text-[11px]" {...props} />
                    </div>
                  ),
                  thead: ({ node, ...props }) => <thead className="bg-cyan-950/80 font-bold text-cyan-300" {...props} />,
                  tbody: ({ node, ...props }) => <tbody className="divide-y divide-cyan-500/20 bg-slate-900/60" {...props} />,
                  tr: ({ node, ...props }) => <tr className="hover:bg-cyan-500/10 transition-colors" {...props} />,
                  th: ({ node, ...props }) => <th className="px-2 py-1 text-left text-cyan-300 font-semibold border-b border-cyan-500/30" {...props} />,
                  td: ({ node, ...props }) => <td className="px-2 py-1 border-b border-cyan-500/10" {...props} />,
                  code: ({ node, inline, className, children, ...props }) => (
                    <code className="bg-slate-950 border border-cyan-500/30 rounded px-1 py-0.5 font-mono text-[10px] text-cyan-300 inline-block" {...props}>
                      {children}
                    </code>
                  ),
                  pre: ({ node, ...props }) => (
                    <pre className="bg-slate-950 p-2 rounded-lg border border-cyan-500/30 overflow-x-auto my-2 font-mono text-[10px] text-cyan-200" {...props} />
                  ),
                  p: ({ node, ...props }) => <p className="leading-relaxed my-0.5" {...props} />,
                  ul: ({ node, ...props }) => <ul className="list-disc list-inside my-1 space-y-0.5 pl-1" {...props} />,
                  ol: ({ node, ...props }) => <ol className="list-decimal list-inside my-1 space-y-0.5 pl-1" {...props} />,
                  h1: ({ node, ...props }) => <h1 className="text-xs font-bold text-cyan-300 my-1" {...props} />,
                  h2: ({ node, ...props }) => <h2 className="text-xs font-bold text-cyan-300 my-1" {...props} />,
                  h3: ({ node, ...props }) => <h3 className="text-[11px] font-bold text-cyan-300 my-0.5" {...props} />,
                  strong: ({ node, ...props }) => <strong className="font-bold text-cyan-300" {...props} />,
                  em: ({ node, ...props }) => <em className="italic text-cyan-200" {...props} />,
                }}
              >
                {msg.text}
              </ReactMarkdown>
            </div>
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
