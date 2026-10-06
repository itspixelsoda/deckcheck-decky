import { Focusable } from "@decky/ui";
import type { CSSProperties, ReactNode } from "react";
import { duration, hours, WEEKDAYS } from "./format";

export const COLORS = { surface: "#18222f", raised: "#223144", ink: "#eef3f8", ink2: "#a9b7c6", muted: "#7c8da3", line: "rgba(255,255,255,0.09)", lo: "#1c2b3f", hi: "#86b6ef", series: "#5598e7" };

const heat = (ratio: number): CSSProperties => ({ background: `color-mix(in oklab, ${COLORS.hi} ${Math.round(ratio * 100)}%, ${COLORS.lo})` });

/** A block the gamepad can land on, so the D-pad scrolls through a page that has no buttons of its own. */
export function Card({ title, note, children }: { title: string; note?: string; children: ReactNode }) {
  return (
    <Focusable onActivate={() => {}} style={{ background: COLORS.surface, border: `1px solid ${COLORS.line}`, borderRadius: 10, padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      <div>
        <div style={{ fontSize: 17, fontWeight: 700 }}>{title}</div>
        {note && <div style={{ fontSize: 12, color: COLORS.ink2, marginTop: 2 }}>{note}</div>}
      </div>
      {children}
    </Focusable>
  );
}

export function Tile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div style={{ background: COLORS.surface, border: `1px solid ${COLORS.line}`, borderRadius: 10, padding: "12px 14px", minWidth: 0 }}>
      <div style={{ fontSize: 12, color: COLORS.ink2 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: COLORS.muted }}>{sub}</div>}
    </div>
  );
}

/** Vertical bars on one scale, with the value printed above the tallest and a label under each (or every `labelEvery`-th). */
export function Columns({ values, labels, labelEvery = 1, height = 120 }: { values: number[]; labels: string[]; labelEvery?: number; height?: number }) {
  const max = Math.max(...values, 1);
  const peak = values.indexOf(Math.max(...values));
  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: `repeat(${values.length}, 1fr)`, gap: 3, alignItems: "end", height }}>
        {values.map((v, i) => (
          <div key={i} style={{ display: "flex", flexDirection: "column", justifyContent: "flex-end", height: "100%", minWidth: 0 }}>
            {i === peak && v > 0 && <div style={{ fontSize: 10, color: COLORS.ink2, textAlign: "center", whiteSpace: "nowrap" }}>{hours(v)}</div>}
            <div style={{ height: `${(v / max) * 82}%`, minHeight: v > 0 ? 2 : 0, background: COLORS.series, borderRadius: "3px 3px 0 0" }} />
          </div>
        ))}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: `repeat(${values.length}, 1fr)`, gap: 3, marginTop: 4 }}>
        {labels.map((l, i) => (
          <div key={i} style={{ fontSize: 10, color: COLORS.muted, textAlign: "center", whiteSpace: "nowrap", overflow: "visible" }}>{i % labelEvery === 0 ? l : ""}</div>
        ))}
      </div>
    </div>
  );
}

/** One column per week, Monday on top, newest week on the right. */
export function Calendar({ days }: { days: { date: string; weekday: number; seconds: number }[] }) {
  const max = Math.max(...days.map((d) => d.seconds), 1);
  const weeks: (typeof days)[] = [];
  for (const d of days) {
    if (!weeks.length || d.weekday === 0) weeks.push([]);
    weeks[weeks.length - 1].push(d);
  }
  const cell = 16;
  return (
    <div style={{ display: "flex", gap: 6 }}>
      <div style={{ display: "grid", gridTemplateRows: `repeat(7, ${cell}px)`, gap: 3, fontSize: 10, color: COLORS.muted }}>
        {WEEKDAYS.map((w, i) => (
          <div key={w} style={{ lineHeight: `${cell}px` }}>{i % 2 === 0 ? w : ""}</div>
        ))}
      </div>
      <div style={{ display: "flex", gap: 3 }}>
        {weeks.map((week, wi) => (
          <div key={wi} style={{ display: "grid", gridTemplateRows: `repeat(7, ${cell}px)`, gap: 3 }}>
            {week.map((d) => (
              <div
                key={d.date}
                title={`${d.date}: ${duration(d.seconds)}`}
                style={{ gridRow: d.weekday + 1, width: cell, height: cell, borderRadius: 3, ...(d.seconds > 0 ? heat(0.15 + 0.85 * (d.seconds / max)) : { background: COLORS.lo }) }}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

export function HourGrid({ grid }: { grid: number[][] }) {
  const max = Math.max(...grid.flat(), 1);
  return (
    <div style={{ display: "grid", gridTemplateColumns: "34px repeat(24, 1fr)", gap: 2, alignItems: "center" }}>
      <div />
      {Array.from({ length: 24 }, (_, h) => (
        <div key={h} style={{ fontSize: 10, color: COLORS.muted, textAlign: "center" }}>{h % 3 === 0 ? h : ""}</div>
      ))}
      {grid.map((row, w) => (
        <Row key={w} label={WEEKDAYS[w]}>
          {row.map((v, h) => (
            <div key={h} title={`${WEEKDAYS[w]} ${h}:00, ${duration(v)}`} style={{ height: 18, borderRadius: 3, ...(v > 0 ? heat(0.15 + 0.85 * (v / max)) : { background: COLORS.lo }) }} />
          ))}
        </Row>
      ))}
    </div>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <div style={{ fontSize: 11, color: COLORS.ink2 }}>{label}</div>
      {children}
    </>
  );
}

export function BarRow({ label, value, max, right }: { label: string; value: number; max: number; right: string }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 260px) 1fr 110px", gap: 12, alignItems: "center" }}>
      <div style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{label}</div>
      <div style={{ height: 12, borderRadius: 4, background: "rgba(255,255,255,0.05)" }}>
        {value > 0 && <div style={{ height: "100%", width: `${Math.max(1, (value / Math.max(max, 1)) * 100)}%`, background: COLORS.series, borderRadius: 4 }} />}
      </div>
      <div style={{ textAlign: "right", color: COLORS.ink2, fontVariantNumeric: "tabular-nums", whiteSpace: "nowrap" }}>{right}</div>
    </div>
  );
}
