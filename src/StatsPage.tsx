import { ConfirmModal, DialogButton, Focusable, Tabs, showModal } from "@decky/ui";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { deleteSession, exportSessions, getSessions, getSummary, startShare, stopShare, type GameTotal, type RangeKey, type Session, type Summary } from "./backend";
import { BarRow, COLORS, Calendar, Card, Columns, HourGrid, Tile } from "./charts";
import { dateTime, day, duration, hours, WEEKDAYS } from "./format";

const RANGES: [RangeKey, string][] = [["7d", "7 days"], ["30d", "30 days"], ["year", "Year"], ["all", "All time"]];
const PAGE = 40;

function Scroll({ children }: { children: ReactNode }) {
  return <div style={{ padding: "16px 28px 90px", display: "flex", flexDirection: "column", gap: 14, height: "100%", overflowY: "auto", boxSizing: "border-box" }}>{children}</div>;
}

function RangePicker({ value, onChange }: { value: RangeKey; onChange: (r: RangeKey) => void }) {
  return (
    <Focusable flow-children="horizontal" style={{ display: "flex", gap: 8 }}>
      {RANGES.map(([key, label]) => (
        <DialogButton key={key} onClick={() => onChange(key)} style={{ minWidth: 0, width: "auto", padding: "6px 16px", ...(key === value ? { background: COLORS.ink, color: "#0f1620" } : {}) }}>
          {label}
        </DialogButton>
      ))}
    </Focusable>
  );
}

function useSummary(range: RangeKey, appid: number | null, version: number) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let current = true;
    getSummary(range, appid).then(
      (s) => current && (setSummary(s), setError(null)),
      (e) => current && setError(String(e)),
    );
    return () => {
      current = false;
    };
  }, [range, appid, version]);
  return { summary, error };
}

function Tiles({ s }: { s: Summary }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
      <Tile label="Play time" value={hours(s.totals.seconds)} sub={`${s.totals.daysPlayed} days played`} />
      <Tile label="Sessions" value={String(s.totals.sessions)} sub={`average ${duration(s.totals.averageSession)}`} />
      <Tile label="Games" value={String(s.totals.games)} />
      <Tile label="Today" value={duration(s.today)} />
      <Tile label="Last 7 days" value={hours(s.week)} />
      <Tile label="Longest session" value={s.longest ? duration(s.longest.activeSeconds) : "-"} sub={s.longest ? `${s.longest.name}, ${day(s.longest.start)}` : undefined} />
    </div>
  );
}

function Empty() {
  return (
    <Card title="Nothing recorded yet">
      <div style={{ color: COLORS.ink2 }}>Sessions appear here after you start and close a game. Launches shorter than 10 seconds are ignored.</div>
    </Card>
  );
}

function Overview({ s }: { s: Summary }) {
  if (!s.totals.sessions) return <Empty />;
  const top = s.games.slice(0, 8);
  return (
    <>
      <Tiles s={s} />
      <Card title="Most played">
        {top.map((g) => (
          <BarRow key={`${g.appid}:${g.nonSteam}`} label={g.name} value={g.seconds} max={top[0].seconds} right={hours(g.seconds)} />
        ))}
      </Card>
      <Card title="Session length" note="Number of sessions by how long you actually played.">
        <Columns values={s.lengths.map((l) => l.sessions * 3600)} labels={s.lengths.map((l) => `${l.label} (${l.sessions})`)} height={90} />
      </Card>
    </>
  );
}

function Patterns({ s }: { s: Summary }) {
  return (
    <>
      <Card title="Last 26 weeks" note="Each square is a day; brighter means more play time.">
        <Calendar days={s.calendar} />
      </Card>
      <Card title="Time of day" note="Play time by hour of the day, in this device's time zone.">
        <Columns values={s.hours} labels={s.hours.map((_, h) => String(h))} labelEvery={2} />
      </Card>
      <Card title="Day of week">
        <Columns values={s.weekdays} labels={WEEKDAYS} height={100} />
      </Card>
      <Card title="Week at a glance" note="Rows are days, columns are hours.">
        <HourGrid grid={s.grid} />
      </Card>
    </>
  );
}

function SessionList({ appid, version, onChanged }: { appid: number | null; version: number; onChanged: () => void }) {
  const [rows, setRows] = useState<Session[]>([]);
  const [total, setTotal] = useState(0);
  const [limit, setLimit] = useState(PAGE);
  useEffect(() => {
    getSessions(limit, 0, appid).then((r) => (setRows(r.sessions), setTotal(r.total)), () => undefined);
  }, [appid, limit, version]);

  const remove = (s: Session) =>
    showModal(
      <ConfirmModal
        strTitle="Delete this session?"
        strDescription={`${s.name}, ${dateTime(s.start)}, ${duration(s.activeSeconds)}. This cannot be undone.`}
        strOKButtonText="Delete"
        onOK={() => deleteSession(s.id).then(onChanged)}
      />,
    );

  if (!rows.length) return <div style={{ color: COLORS.ink2 }}>No sessions.</div>;
  return (
    <>
      {rows.map((s) => (
        <Focusable key={s.id} flow-children="horizontal" style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) 150px 110px 110px 90px", gap: 12, alignItems: "center", padding: "6px 0", borderBottom: `1px solid ${COLORS.line}` }}>
          <div style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{s.name}</div>
          <div style={{ color: COLORS.ink2 }}>{dateTime(s.start)}</div>
          <div style={{ textAlign: "right" }}>{s.open ? "playing" : duration(s.activeSeconds)}</div>
          <div style={{ textAlign: "right", color: COLORS.muted }}>{s.suspendedSeconds >= 60 ? `asleep ${duration(s.suspendedSeconds)}` : ""}</div>
          <DialogButton disabled={s.open} onClick={() => remove(s)} style={{ minWidth: 0, padding: "4px 8px", fontSize: 12 }}>Delete</DialogButton>
        </Focusable>
      ))}
      {rows.length < total && <DialogButton onClick={() => setLimit(limit + PAGE)}>Show more ({total - rows.length} left)</DialogButton>}
    </>
  );
}

function GameDetail({ game, range, version, onBack, onChanged }: { game: GameTotal; range: RangeKey; version: number; onBack: () => void; onChanged: () => void }) {
  const { summary } = useSummary(range, game.appid, version);
  return (
    <>
      <Focusable style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <DialogButton onClick={onBack} style={{ minWidth: 0, width: "auto", padding: "6px 16px" }}>Back</DialogButton>
        <div style={{ fontSize: 22, fontWeight: 700, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{game.name}</div>
      </Focusable>
      {summary && (
        <>
          <Tiles s={summary} />
          <Card title="Last 26 weeks">
            <Calendar days={summary.calendar} />
          </Card>
          <Card title="Time of day">
            <Columns values={summary.hours} labels={summary.hours.map((_, h) => String(h))} labelEvery={2} height={90} />
          </Card>
        </>
      )}
      <div style={{ fontSize: 17, fontWeight: 700 }}>Sessions</div>
      <SessionList appid={game.appid} version={version} onChanged={onChanged} />
    </>
  );
}

function Games({ s, onOpen }: { s: Summary; onOpen: (g: GameTotal) => void }) {
  if (!s.games.length) return <Empty />;
  return (
    <>
      {s.games.map((g) => (
        <Focusable key={`${g.appid}:${g.nonSteam}`} onActivate={() => onOpen(g)} onClick={() => onOpen(g)} style={{ background: COLORS.surface, border: `1px solid ${COLORS.line}`, borderRadius: 8, padding: "10px 14px" }}>
          <BarRow label={g.name} value={g.seconds} max={s.games[0].seconds} right={`${hours(g.seconds)}, ${g.sessions}×`} />
          <div style={{ fontSize: 11, color: COLORS.muted, marginTop: 4 }}>
            last played {day(g.last)}{g.nonSteam ? ", non-Steam" : ""}
          </div>
        </Focusable>
      ))}
    </>
  );
}

function Export() {
  const [saved, setSaved] = useState<{ path: string; sessions: number } | null>(null);
  const [shared, setShared] = useState<{ url: string; seconds: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fail = (e: unknown) => setError(String(e));
  // Leaving the page closes the temporary download address.
  useEffect(() => () => void stopShare().catch(() => undefined), []);

  return (
    <>
      <Card title="Export sessions" note="Writes every finished session to one JSON file. The format is documented in the plugin's README, so any tool can read it.">
        <DialogButton onClick={() => exportSessions().then((r) => (setSaved(r), setError(null)), fail)}>Save file on this device</DialogButton>
        {saved && (
          <div style={{ color: COLORS.ink2 }}>
            Saved {saved.sessions} sessions to <span style={{ color: COLORS.ink }}>{saved.path}</span>
          </div>
        )}
      </Card>
      <Card title="Download on another device" note="Makes the file available on your local network for 10 minutes. Open the address in a browser on a computer connected to the same network.">
        {shared ? (
          <>
            <div style={{ fontSize: 20, fontWeight: 700, wordBreak: "break-all" }}>{shared.url}</div>
            <div style={{ color: COLORS.ink2 }}>Anyone on this network who has this exact address can download the file until you stop sharing.</div>
            <DialogButton onClick={() => stopShare().then(() => setShared(null), fail)}>Stop sharing</DialogButton>
          </>
        ) : (
          <DialogButton onClick={() => startShare().then((r) => (setShared(r), setSaved(r), setError(null)), fail)}>Share on local network</DialogButton>
        )}
      </Card>
      {error && <div style={{ color: "#e66767" }}>{error}</div>}
    </>
  );
}

export function StatsPage() {
  const [tab, setTab] = useState("overview");
  const [range, setRange] = useState<RangeKey>("30d");
  const [version, setVersion] = useState(0);
  const [game, setGame] = useState<GameTotal | null>(null);
  const { summary, error } = useSummary(range, null, version);
  const refresh = useCallback(() => setVersion((v) => v + 1), []);

  const withRange = (body: ReactNode) => (
    <Scroll>
      <RangePicker value={range} onChange={setRange} />
      {error && <div style={{ color: "#e66767" }}>Could not load statistics: {error}</div>}
      {body}
    </Scroll>
  );

  return (
    <div style={{ marginTop: 40, height: "calc(100% - 40px)", background: "#0f1620", color: COLORS.ink }}>
      <Tabs
        activeTab={tab}
        onShowTab={(id: string) => {
          setTab(id);
          setGame(null);
        }}
        autoFocusContents
        tabs={[
          { id: "overview", title: "Overview", content: withRange(summary && <Overview s={summary} />) },
          { id: "patterns", title: "Calendar", content: withRange(summary && <Patterns s={summary} />) },
          {
            id: "games",
            title: "Games",
            content: game ? (
              <Scroll>
                <GameDetail game={game} range={range} version={version} onBack={() => setGame(null)} onChanged={refresh} />
              </Scroll>
            ) : (
              withRange(summary && <Games s={summary} onOpen={setGame} />)
            ),
          },
          { id: "sessions", title: "Sessions", content: <Scroll><SessionList appid={null} version={version} onChanged={refresh} /></Scroll> },
          { id: "export", title: "Export", content: <Scroll><Export /></Scroll> },
        ]}
      />
    </div>
  );
}
