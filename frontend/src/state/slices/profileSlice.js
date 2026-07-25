/**
 * Profile State Slice for Naira-OS
 * Manages user profile information (Name, Role, Handshake status)
 */

export const createProfileSlice = (set) => ({
  userName: 'Boss',
  userRole: 'Lead Architect',
  isHandshakeComplete: false,
  setUserProfile: (profile) =>
    set((state) => ({
      ...state,
      userName: profile.userName ?? profile.name ?? state.userName,
      userRole: profile.userRole ?? profile.role ?? state.userRole,
    })),
  setHandshakeComplete: (complete = true) => set({ isHandshakeComplete: complete }),
});
