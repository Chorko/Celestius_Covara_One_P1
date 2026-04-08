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

interface UserState {
  user: User | null;
  profile: Profile | null;
  setUser: (user: User) => void;
  setProfile: (profile: Profile) => void;
  logout: () => void;
}

export const useUserStore = create<UserState>((set) => ({
  user: null,
  profile: null,
  setUser: (user) => set({ user }),
  setProfile: (profile) => set({ profile }),
  logout: () => set({ user: null, profile: null }),
}));
