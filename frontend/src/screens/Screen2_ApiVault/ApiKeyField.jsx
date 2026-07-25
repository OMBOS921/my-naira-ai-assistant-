import React, { useState } from 'react';

/**
 * ApiKeyField Component
 * Secure input field with tech-styled labels, inline direct 'GET KEY' link badge, show/hide secret toggle, and cyan focus glow.
 */
export const ApiKeyField = ({
  id,
  label = 'API Key',
  placeholder = 'Enter API Key...',
  value,
  onChange,
  required = false,
  status = 'REQUIRED',
  helpLink,
  helpLinkText,
  helperText,
  className = '',
}) => {
  const [showSecret, setShowSecret] = useState(false);

  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      {/* Field Label & Status Badge / Direct Get API Link */}
      <div className="flex justify-between items-center text-xs font-mono">
        <label htmlFor={id} className="text-cyan-300 font-bold tracking-wider flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 shadow-[0_0_6px_#22d3ee]" />
          {label}
        </label>
        <div className="flex items-center gap-2">
          {helpLink && (
            <a
              href={helpLink}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[10px] px-2 py-0.5 rounded bg-cyan-950/80 border border-cyan-400/50 text-cyan-300 hover:text-white hover:bg-cyan-900 transition-colors font-mono font-bold flex items-center gap-1 cursor-pointer"
              title={`Get API Key at ${helpLink}`}
            >
              <span>{helpLinkText || 'GET KEY'}</span>
              <svg className="w-3 h-3 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
            </a>
          )}
          <span
            className={`text-[10px] px-2 py-0.5 rounded-md uppercase tracking-widest border font-mono font-bold ${
              value
                ? 'bg-emerald-950 border-emerald-400 text-emerald-300'
                : required
                ? 'bg-amber-950 border-amber-400 text-amber-300'
                : 'bg-slate-900 border-slate-700 text-slate-300'
            }`}
          >
            {value ? 'SET' : status}
          </span>
        </div>
      </div>

      {/* Input Field with Show/Hide Toggle Button */}
      <div className="relative flex items-center">
        <input
          id={id}
          type={showSecret ? 'text' : 'password'}
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          className="w-full px-3.5 py-2.5 pr-11 bg-slate-950 border border-cyan-500/50 rounded-xl font-mono text-xs text-white placeholder-cyan-600/70 focus:border-cyan-400 focus:shadow-[0_0_15px_rgba(34,211,238,0.3)] transition-all outline-none"
        />

        <button
          type="button"
          onClick={() => setShowSecret(!showSecret)}
          className="absolute right-3 p-1 text-cyan-400 hover:text-cyan-200 transition-colors cursor-pointer"
          title={showSecret ? 'Hide secret key' : 'Show secret key'}
        >
          {showSecret ? (
            /* Eye Off Icon */
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M13.875 18.825A10.05 10.05 0 0112 19c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24M1 1l22 22"
              />
            </svg>
          ) : (
            /* Eye Icon */
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
              />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
              />
            </svg>
          )}
        </button>
      </div>

      {/* Optional Subtle Endpoint Note */}
      {helperText && (
        <span className="text-[10px] font-mono text-cyan-300/80 leading-normal pl-0.5">
          {helperText}
        </span>
      )}
    </div>
  );
};

export default ApiKeyField;
