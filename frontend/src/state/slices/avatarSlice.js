/**
 * Avatar State Slice for Naira-OS
 * Manages discrete avatar rendering modes: 'idle' | 'greeting' | 'listening' | 'speaking' | 'thinking'
 */

export const AVATAR_MODES = {
  IDLE: 'idle',
  GREETING: 'greeting',
  LISTENING: 'listening',
  SPEAKING: 'speaking',
  THINKING: 'thinking',
};

export const createAvatarSlice = (set) => ({
  avatarMode: AVATAR_MODES.IDLE,
  setAvatarMode: (mode) => set({ avatarMode: mode }),
});
