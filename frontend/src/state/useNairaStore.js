import { create } from 'zustand';
import { createAvatarSlice } from './slices/avatarSlice';
import { createProfileSlice } from './slices/profileSlice';

/**
 * Root Zustand store for Naira-OS.
 * Combines modular slices for avatar state, user profile, system status, and UI state.
 */
export const useNairaStore = create((set, get, api) => ({
  ...createAvatarSlice(set, get, api),
  ...createProfileSlice(set, get, api),
  isMicListening: false,
  setMicListening: (isMicListening) => set({ isMicListening }),
  spokenText: '',
  setSpokenText: (spokenText) => set({ spokenText }),
}));

export default useNairaStore;
