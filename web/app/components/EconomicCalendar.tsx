'use client';

import { useState, useEffect, useMemo, useCallback } from "react";
import { fetchEconomicCalendar, analyzeNewsEvent, type EconomicEvent, type NewsAnalysisResponse } from "../../lib/api";

const C = {
  gold: "#D4B483",
  goldDim: "rgba(212,175,55,0.12)",
  green: "#22d3a0",
  greenBright: "#10b981",
  greenDim: "rgba(34,211,160,0.12)",
  red: "#f43f5e",
  redDim: "rgba(244,63,94,0.12)",
  blue: "#38bdf8",
  cyan: "#06b6d4",
  cyanDim: "rgba(6,182,212,0.12)",
  amber: "#f59e0b",
  amberDim: "rgba(245,158,11,0.12)",
  text: "#f8fafc",
  textBright: "#ffffff",
  dim: "#cbd5e1",
  muted: "#64748b",
  faint: "#475569",
  border: "rgba(255,255,255,0.06)",
  mono: '"JetBrains Mono", monospace',
  sans: '"Inter", -apple-system, BlinkMacSystemFont, sans-serif',
};

const impactConfig = {
  HIGH: { bg: "rgba(244,63,94,0.15)", text: "#f43f5e", border: "rgba(244,63,94,0.4)" },
  MED: { bg: "rgba(245,158,11,0.15)", text: "#f59e0b", border: "rgba(245,158,11,0.4)" },
  LOW: { bg: "rgba(100,116,139,0.1)", text: "#94a3b8", border: "rgba(100,116,139,0.25)" },
};

function cleanVal(val?: string | null): string {
  if (!val || val === "N/A" || val === "N" || val === "None" || val.trim() === "") return "--";
  return val.trim();
}

function formatVietnamTime(isoStr: string): string {
  if (!isoStr) return "12:00";
  try {
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) return isoStr.length >= 16 ? isoStr.slice(11, 16) : "12:00";
    return d.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Asia/Ho_Chi_Minh" });
  } catch { return isoStr.length >= 16 ? isoStr.slice(11, 16) : "12:00"; }
}

function getWeekDays(): Date[] {
  const now = new Date();
  const monday = new Date(now);
  monday.setDate(now.getDate() - (now.getDay() === 0 ? 6 : now.getDay() - 1));
  monday.setHours(0, 0, 0, 0);
  return Array.from({ length: 7 }, (_, i) => { const d = new Date(monday); d.setDate(monday.getDate() + i); return d; });
}

function formatCountdown(target: Date): string {
  const diff = target.getTime() - Date.now();
  if (diff <= 0) return "LIVE";
  const h = Math.floor(diff / 3600000);
  const m = Math.floor((diff % 3600000) / 60000);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function UpcomingEventRow({ evt, onClick }: { evt: EconomicEvent; onClick: (e: EconomicEvent) => void }) {
  const impactKey = evt.impact?.toUpperCase() as keyof typeof impactConfig;
  const ic = impactConfig[impactKey] || impactConfig.LOW;
  const evtTime = new Date(evt.datetime);

  return (
    <div onClick={() => onClick(evt)} style={{
      padding: "5px 8px",
      background: `linear-gradient(90deg, rgba(6,182,212,0.08) 0%, rgba(5,7,12,0.9) 100%)`,
      borderLeft: `3px solid ${ic.text}`,
      borderTop: `1px solid ${ic.border}`,
      borderRight: `1px solid ${ic.border}`,
      borderBottom: `1px solid ${ic.border}`,
      borderRadius: 4, cursor: "pointer", transition: "all 0.2s ease",
      display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginBottom: 3,
    }}
      onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.background = `linear-gradient(90deg, rgba(6,182,212,0.18) 0%, rgba(10,14,24,0.95) 100%)`; (e.currentTarget as HTMLDivElement).style.borderColor = C.gold; }}
      onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.background = `linear-gradient(90deg, rgba(6,182,212,0.08) 0%, rgba(5,7,12,0.9) 100%)`; (e.currentTarget as HTMLDivElement).style.borderColor = ic.border; }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0, minWidth: 70 }}>
        <span style={{ fontSize: 8, fontFamily: C.mono, color: C.textBright, fontWeight: 700, background: "rgba(0,0,0,0.4)", padding: "2px 5px", borderRadius: 3 }}>{formatVietnamTime(evt.datetime)}</span>
        <div style={{ width: 20, height: 14, borderRadius: 2, background: "linear-gradient(135deg, rgba(212,175,55,0.2) 0%, rgba(10,14,24,0.8) 100%)", border: "1px solid rgba(212,175,55,0.3)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 7, fontFamily: C.mono, color: C.gold, fontWeight: 800 }}>{evt.currency}</div>
      </div>
      <div style={{ fontSize: 8.5, color: "#fff", fontFamily: C.sans, fontWeight: 600, flex: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{evt.title}</div>
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
        <span style={{ fontSize: 7, fontFamily: C.mono, color: C.dim }}>FC: <strong style={{ color: C.gold }}>{cleanVal(evt.forecast)}</strong></span>
        <span style={{ fontSize: 7, fontFamily: C.mono, color: C.muted }}>PR: <strong style={{ color: C.dim }}>{cleanVal(evt.previous)}</strong></span>
        <div style={{ padding: "2px 6px", background: C.cyanDim, border: "1px solid #06b6d4", borderRadius: 3, boxShadow: "0 0 8px rgba(6,182,212,0.3)" }}>
          <span style={{ fontSize: 7, fontFamily: C.mono, fontWeight: 800, color: C.cyan }}>{formatCountdown(evtTime)}</span>
        </div>
      </div>
    </div>
  );
}

function PastEventRow({ evt }: { evt: EconomicEvent }) {
  return (
    <div style={{ padding: "4px 8px", background: "rgba(0,0,0,0.25)", border: "1px solid rgba(255,255,255,0.03)", borderRadius: 4, opacity: 0.4, pointerEvents: "none", display: "flex", alignItems: "center", gap: 8, marginBottom: 2, filter: "grayscale(60%)" }}>
      <span style={{ fontSize: 7, fontFamily: C.mono, color: C.muted, minWidth: 50 }}>{formatVietnamTime(evt.datetime)}</span>
      <div style={{ width: 18, height: 12, borderRadius: 2, background: "rgba(255,255,255,0.05)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 6, fontFamily: C.mono, color: C.muted, fontWeight: 700 }}>{evt.currency}</div>
      <span style={{ fontSize: 7.5, color: C.muted, fontFamily: C.sans, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{evt.title}</span>
      <span style={{ fontSize: 7, fontFamily: C.mono, color: C.faint }}>ACT: {cleanVal(evt.actual)}</span>
    </div>
  );
}

function SkeletonRow() {
  return (
    <div style={{ height: 28, padding: "4px 8px", marginBottom: 3, background: "rgba(0,0,0,0.2)", borderRadius: 4, border: "1px solid rgba(255,255,255,0.03)", display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{ width: 40, height: 10, background: "rgba(255,255,255,0.04)", borderRadius: 2, animation: "pulse 1.5s infinite" }} />
      <div style={{ flex: 1, height: 10, background: "rgba(255,255,255,0.04)", borderRadius: 2, animation: "pulse 1.5s infinite" }} />
      <div style={{ width: 50, height: 10, background: "rgba(255,255,255,0.03)", borderRadius: 2, animation: "pulse 1.5s infinite" }} />
    </div>
  );
}

interface EconomicCalendarProps {
  onEventSelect?: (event: EconomicEvent) => void;
}

export default function EconomicCalendar({ onEventSelect }: EconomicCalendarProps) {
  const [events, setEvents] = useState<EconomicEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedDay, setSelectedDay] = useState<number>(new Date().getDay() === 0 ? 6 : new Date().getDay() - 1);
  const [showAllWeek, setShowAllWeek] = useState(false);
  const [selectedModalEvent, setSelectedModalEvent] = useState<EconomicEvent | null>(null);
  const [analysis, setAnalysis] = useState<NewsAnalysisResponse | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [filterImpact, setFilterImpact] = useState<string>("ALL");

  const weekDays = useMemo(() => getWeekDays(), []);
  const todayIdx = useMemo(() => { const now = new Date(); return now.getDay() === 0 ? 6 : now.getDay() - 1; }, []);

  const loadEvents = useCallback(async () => {
    try {
      const data = await fetchEconomicCalendar(7);
      if (data) setEvents(data);
    } catch { /* silent */ } finally { setLoading(false); }
  }, []);

  useEffect(() => { loadEvents(); const interval = setInterval(loadEvents, 60000); return () => clearInterval(interval); }, [loadEvents]);

  const filteredEvents = useMemo(() => {
    return events.filter(e => filterImpact === "ALL" || e.impact?.toUpperCase() === filterImpact);
  }, [events, filterImpact]);

  const dayEvents = useMemo(() => {
    if (showAllWeek) return filteredEvents;
    const day = weekDays[selectedDay];
    if (!day) return [];
    const targetM = day.getMonth() + 1;
    const targetD = day.getDate();
    return filteredEvents.filter(e => {
      if (!e.datetime) return false;
      const d = new Date(e.datetime);
      if (isNaN(d.getTime())) return false;
      return d.getMonth() + 1 === targetM && d.getDate() === targetD;
    });
  }, [filteredEvents, selectedDay, weekDays, showAllWeek]);

  const highImpactCounts = useMemo(() => weekDays.map(d => {
    const m = d.getMonth() + 1, t = d.getDate();
    return events.filter(e => e.impact?.toUpperCase() === "HIGH" && e.datetime && new Date(e.datetime).getMonth() + 1 === m && new Date(e.datetime).getDate() === t).length;
  }), [events, weekDays]);

  const now = new Date();
  const upcoming = useMemo(() => dayEvents.filter(e => e.status === "upcoming" || e.status === "live" || new Date(e.datetime) >= now).sort((a, b) => new Date(a.datetime).getTime() - new Date(b.datetime).getTime()), [dayEvents, now]);
  const past = useMemo(() => dayEvents.filter(e => e.status === "released" || new Date(e.datetime) < now).sort((a, b) => new Date(b.datetime).getTime() - new Date(a.datetime).getTime()), [dayEvents, now]);

  const handleEventClick = useCallback((evt: EconomicEvent) => {
    setSelectedModalEvent(evt);
    setAnalyzing(true);
    setAnalysis(null);
    analyzeNewsEvent({ title: evt.title, impact: evt.impact, actual: evt.actual || "", forecast: evt.forecast || "", previous: evt.previous || "", date: evt.datetime?.slice(0, 10) || "", time: formatVietnamTime(evt.datetime) })
      .then(res => { setAnalysis(res); setAnalyzing(false); });
    onEventSelect?.(evt);
  }, [onEventSelect]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4, height: "100%", minHeight: 0, background: "rgba(5,7,12,0.95)", border: "1px solid rgba(255,255,255,0.05)", borderRadius: 6, padding: 6 }}>
      {/* CONTROLS */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{ width: 6, height: 6, borderRadius: "50%", background: C.greenBright, boxShadow: `0 0 8px ${C.greenBright}` }} />
          <span style={{ fontSize: 8, fontWeight: 800, color: C.text, letterSpacing: "0.08em", fontFamily: C.mono, textTransform: "uppercase" }}>ECONOMIC CALENDAR</span>
          <span style={{ fontSize: 6, fontFamily: C.mono, color: C.cyan, background: C.cyanDim, padding: "1px 4px", borderRadius: 2, border: "1px solid rgba(6,182,212,0.25)" }}>GMT+7</span>
        </div>
        <div style={{ display: "flex", gap: 3, alignItems: "center" }}>
          <button onClick={() => setShowAllWeek(!showAllWeek)} style={{ padding: "2px 6px", fontSize: 7, fontFamily: C.mono, cursor: "pointer", background: showAllWeek ? C.goldDim : "transparent", border: `1px solid ${showAllWeek ? C.gold : C.border}`, borderRadius: 3, color: showAllWeek ? C.gold : C.muted, fontWeight: showAllWeek ? 800 : 500 }}>{showAllWeek ? "ALL" : "DAY"}</button>
          {["ALL", "HIGH", "MED", "LOW"].map(opt => {
            const isAct = filterImpact === opt;
            const btnColor = opt === "HIGH" ? C.red : opt === "MED" ? C.amber : opt === "LOW" ? C.muted : C.blue;
            return <button key={opt} onClick={() => setFilterImpact(opt)} style={{ padding: "2px 5px", fontSize: 7, fontFamily: C.mono, cursor: "pointer", background: isAct ? `rgba(${opt === "HIGH" ? "244,63,94" : opt === "MED" ? "245,158,11" : "59,130,246"}, 0.2)` : "rgba(255,255,255,0.02)", border: `1px solid ${isAct ? btnColor : C.border}`, borderRadius: 3, color: isAct ? "#fff" : C.muted, fontWeight: isAct ? 800 : 500, transition: "all 0.15s ease" }}>{opt}</button>;
          })}
        </div>
      </div>

      {/* DAY RIBBON */}
      {!showAllWeek && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 3, flexShrink: 0 }}>
          {weekDays.map((d, i) => {
            const isActive = i === selectedDay;
            const isToday = i === todayIdx;
            const dateStr = d.toLocaleDateString("vi-VN", { day: "numeric", month: "numeric" });
            const highCount = highImpactCounts[i] || 0;
            return (
              <button key={`day-${i}`} onClick={() => setSelectedDay(i)} style={{
                height: 20, padding: "0 3px", background: isActive ? C.goldDim : isToday ? "rgba(255,255,255,0.04)" : "rgba(255,255,255,0.02)",
                border: `1px solid ${isActive ? C.gold : isToday ? "rgba(212,180,131,0.4)" : C.border}`, borderRadius: 4, cursor: "pointer", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 1, transition: "all 0.15s ease", position: "relative",
              }}>
                <span style={{ fontSize: 7, color: isActive ? C.gold : C.muted, fontFamily: C.mono, fontWeight: 700 }}>{["T2", "T3", "T4", "T5", "T6", "T7", "CN"][i]}</span>
                <span style={{ fontSize: 7, color: isActive ? "#fff" : C.dim, fontFamily: C.mono, fontWeight: isActive ? 800 : 500 }}>{dateStr}</span>
                {highCount > 0 && <div style={{ position: "absolute", top: -3, right: -3, background: C.red, color: "#fff", fontSize: 5, fontFamily: C.mono, fontWeight: 900, width: 10, height: 10, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", boxShadow: `0 0 6px ${C.red}` }}>{highCount}</div>}
              </button>
            );
          })}
        </div>
      )}

      <div style={{ height: 1, background: "rgba(255,255,255,0.05)", flexShrink: 0 }} />

      {/* EVENT LIST */}
      <div style={{ flex: 1, overflowY: "auto", minHeight: 0, display: "flex", flexDirection: "column", gap: 2 }}>
        {loading ? <><SkeletonRow /><SkeletonRow /><SkeletonRow /></> :
         upcoming.length === 0 && past.length === 0 ? (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", color: C.muted, fontFamily: C.mono, fontSize: 8, gap: 6 }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={C.muted} strokeWidth="1.5"><rect x="3" y="4" width="18" height="18" rx="2" /><path d="M16 2v4M8 2v4M3 10h18" /></svg>
            <span>No economic events scheduled</span>
            <button onClick={() => setShowAllWeek(true)} style={{ padding: "4px 10px", fontSize: 7, fontFamily: C.mono, background: C.goldDim, border: `1px solid ${C.gold}`, borderRadius: 4, color: C.gold, fontWeight: 700, cursor: "pointer" }}>VIEW ALL WEEK</button>
          </div>
        ) : (
          <>
            {upcoming.length > 0 && (
              <div>
                <div style={{ fontSize: 7, fontFamily: C.mono, color: C.cyan, fontWeight: 900, letterSpacing: "0.06em", marginBottom: 4, textTransform: "uppercase", display: "flex", alignItems: "center", gap: 6 }}>
                  <div style={{ width: 5, height: 5, borderRadius: "50%", background: C.cyan, boxShadow: `0 0 8px ${C.cyan}` }} />
                  UPCOMING ({upcoming.length})
                </div>
                {upcoming.map((evt, idx) => <UpcomingEventRow key={`${evt.id}-${idx}`} evt={evt} onClick={handleEventClick} />)}
              </div>
            )}
            {past.length > 0 && (
              <div style={{ marginTop: upcoming.length > 0 ? 8 : 0 }}>
                <div style={{ fontSize: 7, fontFamily: C.mono, color: C.muted, fontWeight: 700, letterSpacing: "0.05em", marginBottom: 3, textTransform: "uppercase" }}>RELEASED ({past.length})</div>
                {past.map((evt, idx) => <PastEventRow key={`${evt.id}-${idx}`} evt={evt} />)}
              </div>
            )}
          </>
        )}
      </div>

      {/* AI MODAL */}
      {selectedModalEvent && (
        <div onClick={() => setSelectedModalEvent(null)} style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(2,3,5,0.9)", backdropFilter: "blur(16px)", zIndex: 99999, display: "grid", placeItems: "center", padding: 20 }}>
          <div onClick={e => e.stopPropagation()} className="gradient-border" style={{ background: "linear-gradient(145deg, rgba(8,12,22,0.98) 0%, rgba(3,5,8,0.99) 100%)", borderRadius: 12, width: "100%", maxWidth: 520, padding: "20px 24px", boxShadow: "0 20px 60px rgba(0,0,0,0.9), 0 0 40px rgba(6,182,212,0.2)", color: C.text }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16, paddingBottom: 12, borderBottom: `1px solid ${C.border}` }}>
              <div>
                <div style={{ fontSize: 10, fontWeight: 800, color: C.gold, fontFamily: C.mono, letterSpacing: "0.05em" }}>AI MACRO ASSESSMENT</div>
                <div style={{ fontSize: 8, color: C.muted, fontFamily: C.sans, marginTop: 2 }}>Gold (XAUUSD) Trading Impact Analysis</div>
              </div>
              <button onClick={() => setSelectedModalEvent(null)} style={{ background: "rgba(255,255,255,0.05)", border: `1px solid ${C.border}`, borderRadius: 4, color: C.muted, fontSize: 12, width: 28, height: 28, cursor: "pointer", display: "grid", placeItems: "center" }}>X</button>
            </div>
            <div style={{ background: "rgba(0,0,0,0.4)", border: `1px solid ${C.border}`, borderRadius: 6, padding: "10px 14px", marginBottom: 14 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: C.textBright, fontFamily: C.sans }}>{selectedModalEvent.currency} {selectedModalEvent.title}</div>
                <span style={{ fontSize: 7, fontFamily: C.mono, fontWeight: 900, color: selectedModalEvent.impact === "HIGH" ? C.red : C.amber, background: selectedModalEvent.impact === "HIGH" ? C.redDim : C.amberDim, padding: "2px 8px", borderRadius: 3, border: `1px solid ${selectedModalEvent.impact === "HIGH" ? C.red : C.amber}` }}>{selectedModalEvent.impact}</span>
              </div>
              <div style={{ display: "flex", gap: 16, fontSize: 8, fontFamily: C.mono, color: C.muted }}>
                <span>Time (VN): <strong style={{ color: C.cyan }}>{formatVietnamTime(selectedModalEvent.datetime)}</strong></span>
                <span>Forecast: <strong style={{ color: C.gold }}>{cleanVal(selectedModalEvent.forecast)}</strong></span>
                <span>Previous: <strong style={{ color: C.dim }}>{cleanVal(selectedModalEvent.previous)}</strong></span>
              </div>
            </div>
            {analyzing ? (
              <div style={{ textAlign: "center", padding: 20, color: C.cyan, fontFamily: C.mono, fontSize: 9 }}>
                <div style={{ display: "flex", justifyContent: "center", gap: 6, marginBottom: 8 }}>
                  {[0, 1, 2].map(i => <div key={i} style={{ width: 6, height: 6, borderRadius: "50%", background: C.cyan, animation: `livePulse 1s ease-in-out ${i * 0.2}s infinite` }} />)}
                </div>
                AI analyzing market impact...
              </div>
            ) : (
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14, background: "rgba(0,0,0,0.3)", border: `1px solid ${C.border}`, padding: "10px 14px", borderRadius: 6 }}>
                  <span style={{ fontSize: 8, fontFamily: C.mono, color: C.muted }}>Recommendation:</span>
                  <span style={{ fontSize: 11, fontFamily: C.mono, fontWeight: 900, letterSpacing: "0.05em", padding: "3px 12px", borderRadius: 4, background: analysis?.recommendation === "BUY" ? C.greenDim : analysis?.recommendation === "SELL" ? C.redDim : C.amberDim, color: analysis?.recommendation === "BUY" ? C.greenBright : analysis?.recommendation === "SELL" ? C.red : C.amber, border: `1px solid ${analysis?.recommendation === "BUY" ? C.green : analysis?.recommendation === "SELL" ? C.red : C.amber}` }}>
                    {analysis?.recommendation === "BUY" ? "BUY XAUUSD" : analysis?.recommendation === "SELL" ? "SELL XAUUSD" : "NEUTRAL"}
                  </span>
                </div>
                <div style={{ fontSize: 8.5, fontFamily: C.sans, color: C.dim, lineHeight: 1.6, background: "rgba(0,0,0,0.4)", border: `1px solid ${C.border}`, padding: "12px 14px", borderRadius: 6, maxHeight: 180, overflowY: "auto" }}>
                  {analysis?.analysis || "Analysis complete."}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
