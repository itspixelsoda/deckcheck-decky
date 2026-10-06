import { callable } from "@decky/api";

export interface Session {
  id: string;
  steamid: string | null;
  appid: number;
  name: string;
  nonSteam: boolean;
  start: number;
  end: number;
  open: boolean;
  activeSeconds: number;
  suspendedSeconds: number;
}

export interface GameTotal {
  appid: number;
  name: string;
  nonSteam: boolean;
  seconds: number;
  sessions: number;
  first: number;
  last: number;
}

export interface Summary {
  today: number;
  week: number;
  totals: { seconds: number; sessions: number; games: number; daysPlayed: number; averageSession: number; first: number | null };
  longest: Session | null;
  /** Oldest first; weekday 0 is Monday. */
  calendar: { date: string; weekday: number; seconds: number }[];
  hours: number[];
  weekdays: number[];
  grid: number[][];
  games: GameTotal[];
  lengths: { label: string; sessions: number }[];
}

export interface Live {
  playing: Session[];
  today: number;
  week: number;
  sessions: number;
}

export interface RunningApp {
  appid: number;
  name: string;
  non_steam: boolean;
  steamid: string | null;
}

export type RangeKey = "7d" | "30d" | "year" | "all";

export const gameStarted = callable<[appid: number, name: string, nonSteam: boolean, steamid: string | null], void>("game_started");
export const gameStopped = callable<[appid: number], void>("game_stopped");
export const reconcile = callable<[running: RunningApp[]], void>("reconcile");
export const getLive = callable<[], Live>("get_live");
export const getSummary = callable<[range: RangeKey, appid: number | null], Summary>("get_summary");
export const getSessions = callable<[limit: number, offset: number, appid: number | null], { total: number; sessions: Session[] }>("get_sessions");
export const deleteSession = callable<[id: string], void>("delete_session");
export const exportSessions = callable<[], { path: string; sessions: number }>("export_sessions");
export const startShare = callable<[], { url: string; seconds: number; path: string; sessions: number }>("start_share");
export const stopShare = callable<[], void>("stop_share");
