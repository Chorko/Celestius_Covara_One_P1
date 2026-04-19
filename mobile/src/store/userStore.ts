import { create } from "zustand";
import type { User } from "@supabase/supabase-js";

export interface Profile {
  id: string;
  full_name: string | null;
  email: string | null;
  phone: string | null;
  role: string | null;
  [key: string]: unknown;
}

export type UserRole = "worker" | "insurer_admin" | null;

export interface KycSnapshot {
  aadhaarVerified: boolean;
  bankVerified: boolean;
  phoneVerified: boolean;
  faceVerified: boolean;
  isComplete: boolean;
}

interface SessionSnapshot {
  user: User | null;
  profile: Profile | null;
  role: UserRole;
  needsOnboarding: boolean;
  accessToken: string | null;
}

interface UserState {
  user: User | null;
  profile: Profile | null;
  role: UserRole;
  needsOnboarding: boolean;
  accessToken: string | null;
  kyc: KycSnapshot | null;
  setUser: (user: User | null) => void;
  setProfile: (profile: Profile | null) => void;
  setSessionSnapshot: (snapshot: SessionSnapshot) => void;
  setKyc: (kyc: KycSnapshot | null) => void;
  logout: () => void;
}

export const useUserStore = create<UserState>((set) => ({
  user: null,
  profile: null,
  role: null,
  needsOnboarding: false,
  accessToken: null,
  kyc: null,
  setUser: (user) => set({ user }),
  setProfile: (profile) =>
    set({
      profile,
      role: (profile?.role as UserRole) ?? null,
    }),
  setSessionSnapshot: (snapshot) =>
    set({
      user: snapshot.user,
      profile: snapshot.profile,
      role: snapshot.role,
      needsOnboarding: snapshot.needsOnboarding,
      accessToken: snapshot.accessToken,
    }),
  setKyc: (kyc) => set({ kyc }),
  logout: () =>
    set({
      user: null,
      profile: null,
      role: null,
      needsOnboarding: false,
      accessToken: null,
      kyc: null,
    }),
}));
