import { Router } from "@decky/ui";
import { gameStarted, gameStopped, reconcile, type RunningApp } from "./backend";

// Steam's own value for "this library entry is a non-Steam shortcut".
const APP_TYPE_SHORTCUT = 1073741824;

function currentSteamId(): string | null {
  try {
    const id = (window as unknown as { App?: { m_CurrentUser?: { strSteamID?: string } } }).App?.m_CurrentUser?.strSteamID;
    return id && /^\d{17}$/.test(id) ? id : null;
  } catch {
    return null;
  }
}

function describe(appid: number): RunningApp {
  let name = `App ${appid}`;
  let nonSteam = false;
  try {
    const overview = window.appStore?.GetAppOverviewByAppID(appid) as { display_name?: string; app_type?: number } | null;
    if (overview?.display_name) name = overview.display_name;
    nonSteam = overview?.app_type === APP_TYPE_SHORTCUT;
  } catch {
    // The library can be mid-load; the backend fills the name in when Steam repeats the notification.
  }
  return { appid, name, non_steam: nonSteam, steamid: currentSteamId() };
}

/** Forwards game starts and stops to the backend. Returns a function that stops listening. */
export function startTracking(onChange: () => void): () => void {
  const log = (what: string) => (e: unknown) => console.error(`[deckcheck] ${what} failed`, e);

  // Games already running when the plugin loads (Decky restart, plugin update) never send a start notification.
  let running: RunningApp[] = [];
  try {
    running = (Router.RunningApps ?? []).map((app) => describe(Number(app.appid))).filter((app) => Number.isFinite(app.appid));
  } catch (e) {
    log("listing running apps")(e);
  }
  reconcile(running).then(onChange, log("reconcile"));

  const registration = SteamClient.GameSessions.RegisterForAppLifetimeNotifications((n) => {
    if (n.bRunning) {
      const app = describe(n.unAppID);
      gameStarted(app.appid, app.name, app.non_steam, app.steamid).then(onChange, log("game_started"));
    } else {
      gameStopped(n.unAppID).then(onChange, log("game_stopped"));
    }
  });
  return () => registration.unregister();
}
