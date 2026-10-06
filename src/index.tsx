import { definePlugin, routerHook } from "@decky/api";
import { ButtonItem, Navigation, PanelSection, PanelSectionRow, staticClasses } from "@decky/ui";
import { useEffect, useState } from "react";
import { FaChartBar } from "react-icons/fa";
import { exportSessions, getLive, type Live } from "./backend";
import { duration, hours } from "./format";
import { StatsPage } from "./StatsPage";
import { startTracking } from "./tracking";

const ROUTE = "/deckcheck";

// Lets the quick panel refresh when a game starts or stops while it is open.
const listeners = new Set<() => void>();
const notify = () => listeners.forEach((l) => l());

function QuickPanel() {
  const [live, setLive] = useState<Live | null>(null);
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    const load = () => getLive().then(setLive, (e) => setNote(String(e)));
    load();
    listeners.add(load);
    const timer = setInterval(load, 30_000);
    return () => {
      listeners.delete(load);
      clearInterval(timer);
    };
  }, []);

  return (
    <>
      <PanelSection title="Now">
        <PanelSectionRow>
          <div>
            {live?.playing.length
              ? live.playing.map((s) => (
                  <div key={s.id}>
                    {s.name}: {duration(s.activeSeconds)}
                  </div>
                ))
              : "No game running"}
          </div>
        </PanelSectionRow>
      </PanelSection>
      <PanelSection title="Play time">
        <PanelSectionRow>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span>Today</span>
            <span>{live ? duration(live.today) : "…"}</span>
          </div>
        </PanelSectionRow>
        <PanelSectionRow>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span>Last 7 days</span>
            <span>{live ? hours(live.week) : "…"}</span>
          </div>
        </PanelSectionRow>
        <PanelSectionRow>
          <ButtonItem
            layout="below"
            onClick={() => {
              Navigation.Navigate(ROUTE);
              Navigation.CloseSideMenus();
            }}
          >
            Open statistics
          </ButtonItem>
        </PanelSectionRow>
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={() => exportSessions().then((r) => setNote(`Saved ${r.sessions} sessions to ${r.path}`), (e) => setNote(String(e)))}>
            Export sessions to file
          </ButtonItem>
        </PanelSectionRow>
        {note && (
          <PanelSectionRow>
            <div style={{ fontSize: 12, wordBreak: "break-all" }}>{note}</div>
          </PanelSectionRow>
        )}
      </PanelSection>
    </>
  );
}

export default definePlugin(() => {
  routerHook.addRoute(ROUTE, StatsPage, { exact: true });
  const stopTracking = startTracking(notify);

  return {
    name: "deckcheck",
    titleView: <div className={staticClasses.Title}>deckcheck</div>,
    content: <QuickPanel />,
    icon: <FaChartBar />,
    onDismount() {
      stopTracking();
      routerHook.removeRoute(ROUTE);
    },
  };
});
