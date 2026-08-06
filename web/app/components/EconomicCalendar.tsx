"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import { fetchEconomicCalendar, analyzeNewsEvent, type EconomicEvent, type NewsAnalysisResponse } from "../../lib/api";

const C = {
  bgMain: "#05070c",
  panelBg: "rgba(10, 14, 24, 0.96)",
  border: "rgba(255, 255, 255, 0.08)",
  gold: "#D4B483",
  green: "#22d3a0",
  greenBright: "#10b981",
  red: "#f43f5e",
  blue: "#38bdf8",
  purple: "#a855f7",
  cyan: "#06b6d4",
  amber: "#f59e0b",
  text: "#f8fafc",
  dim: "#cbd5e1",
  muted: "#64748b",
  faint: "#475569",
  mono: '"JetBrains Mono", monospace',
  sans: '"Inter", -apple-system, BlinkMacSystemFont, sans-serif',
};

const impactColors = {
  HIGH: { bg: "rgba(244, 63, 94, 0.25)", text: "#f43f5e", border: "rgba(244, 63, 94, 0.5)" },
  MED: { bg: "rgba(245, 158, 11, 0.25)", text: "#f59e0b", border: "rgba(245, 158, 11, 0.5)" },
  LOW: { bg: "rgba(100, 116, 139, 0.15)", text: "#94a3b8", border: "rgba(100, 116, 139, 0.3)" },
};

const countryFlags: Record<string, string> = {
  USD: "🇺🇸", EUR: "🇪🇺", JPY: "🇯🇵", GBP: "🇬🇧", CHF: "🇨🇭",
  AUD: "🇦🇺", NZD: "🇳🇿", CAD: "🇨🇦", CNY: "🇨🇳", INR: "🇮🇳",
  BRL: "🇧🇷", MXN: "🇲🇽", ZAR: "🇿🇦", KRW: "🇰🇷", SGD: "🇸🇬",
};

function cleanVal(val?: string | null): string {
  if (!val || val === "N/A" || val === "N" || val === "None" || val.trim() === "") return "--";
  return val.trim();
}

function formatVietnamTime(isoStr: string): string {
  if (!isoStr) return "12:00";
  try {
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) {
      return isoStr.length >= 16 ? isoStr.slice(11, 16) : "12:00";
    }
    return d.toLocaleTimeString("vi-VN", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
      timeZone: "Asia/Ho_Chi_Minh",
    });
  } catch {
    return isoStr.length >= 16 ? isoStr.slice(11, 16) : "12:00";
  }
}

function getWeekDays(): Date[] {
  const now = new Date();
  const monday = new Date(now);
  monday.setDate(now.getDate() - (now.getDay() === 0 ? 6 : now.getDay() - 1));
  monday.setHours(0, 0, 0, 0);
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(monday);
    d.setDate(monday.getDate() + i);
    return d;
  });
}

function formatCountdown(target: Date): string {
  const diff = target.getTime() - Date.now();
  if (diff <= 0) return "LIVE";
  const h = Math.floor(diff / 3600000);
  const m = Math.floor((diff % 3600000) / 60000);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function SkeletonRow() {
  return (
    <div style={{ height: "24px", padding: "2px 6px", background: "rgba(255,255,255,0.02)", borderRadius: "3px", border: "1px solid rgba(255,255,255,0.04)", display: "flex", alignItems: "center", gap: "8px" }}>
      <div style={{ width: "30px", height: "10px", background: "rgba(255,255,255,0.06)", borderRadius: "2px", animation: "pulse 1.5s infinite" }} />
      <div style={{ flex: 1, height: "10px", background: "rgba(255,255,255,0.06)", borderRadius: "2px", animation: "pulse 1.5s infinite" }} />
      <div style={{ width: "60px", height: "10px", background: "rgba(255,255,255,0.04)", borderRadius: "2px", animation: "pulse 1.5s infinite" }} />
    </div>
  );
}

function UpcomingEventRow({ evt, onClick }: { evt: EconomicEvent; onClick: (e: EconomicEvent) => void }) {
  const ic = impactColors[evt.impact as keyof typeof impactColors] || impactColors.LOW;
  const flag = countryFlags[evt.currency] || "🌐";
  const evtTime = new Date(evt.datetime);
  const vnTimeStr = formatVietnamTime(evt.datetime);

  return (
    <div
      onClick={() => onClick(evt)}
      title="Bấm để xem AI đánh giá & nhận định MUA/BÁN cho tin tức này"
      style={{
        padding: "3px 6px",
        background: "linear-gradient(90deg, rgba(6, 182, 212, 0.12), rgba(15, 23, 42, 0.8))",
        borderLeft: `3px solid ${ic.text}`,
        borderTop: `1px solid ${ic.border}`,
        borderRight: `1px solid ${ic.border}`,
        borderBottom: `1px solid ${ic.border}`,
        borderRadius: "3px",
        cursor: "pointer",
        transition: "all 0.15s ease",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "6px",
        height: "24px",
        boxSizing: "border-box",
        boxShadow: evt.impact === "HIGH" ? "0 0 8px rgba(244, 63, 94, 0.2)" : "none",
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLDivElement).style.background = "linear-gradient(90deg, rgba(6, 182, 212, 0.25), rgba(30, 41, 59, 0.9))";
        (e.currentTarget as HTMLDivElement).style.borderColor = C.gold;
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLDivElement).style.background = "linear-gradient(90deg, rgba(6, 182, 212, 0.12), rgba(15, 23, 42, 0.8))";
        (e.currentTarget as HTMLDivElement).style.borderColor = ic.border;
      }}
    >
      {/* Left meta */}
      <div style={{ display: "flex", alignItems: "center", gap: "4px", flexShrink: 0 }}>
        <span style={{ fontSize: "7.5px", fontFamily: C.mono, color: C.text, fontWeight: 800, background: "rgba(255,255,255,0.06)", padding: "0 3px", borderRadius: "2px" }}>
          {vnTimeStr}
        </span>
        <span style={{ fontSize: "8.5px" }}>{flag}</span>
        <span style={{ fontSize: "7.5px", fontFamily: C.mono, color: C.text, fontWeight: 700 }}>{evt.currency}</span>
        <span style={{ fontSize: "6px", fontFamily: C.mono, fontWeight: 900, color: ic.text, background: ic.bg, padding: "0 3px", borderRadius: "2px", border: `1px solid ${ic.border}` }}>
          {evt.impact}
        </span>
      </div>

      {/* Title */}
      <div style={{ fontSize: "8px", color: "#fff", fontFamily: C.sans, fontWeight: 700, flex: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
        {evt.title}
      </div>

      {/* Metrics & Countdown */}
      <div style={{ display: "flex", alignItems: "center", gap: "6px", flexShrink: 0, fontSize: "7px", fontFamily: C.mono }}>
        <span style={{ color: C.dim }}>FC: <strong style={{ color: C.gold }}>{cleanVal(evt.forecast)}</strong></span>
        <span style={{ color: C.muted }}>PR: <strong style={{ color: C.dim }}>{cleanVal(evt.previous)}</strong></span>
        <span style={{ color: "#fff", fontWeight: 800, background: "rgba(6, 182, 212, 0.3)", padding: "0 4px", borderRadius: "2px", border: "1px solid #06b6d4", boxShadow: "0 0 6px rgba(6, 182, 212, 0.4)" }}>
          ⏱ {formatCountdown(evtTime)}
        </span>
      </div>
    </div>
  );
}

function PastEventRow({ evt }: { evt: EconomicEvent }) {
  const flag = countryFlags[evt.currency] || "🌐";
  const vnTimeStr = formatVietnamTime(evt.datetime);

  return (
    <div
      style={{
        padding: "3px 6px",
        background: "rgba(10, 14, 24, 0.4)",
        border: "1px stroke rgba(255,255,255,0.03)",
        borderRadius: "3px",
        cursor: "not-allowed",
        opacity: 0.35,
        pointerEvents: "none",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "6px",
        height: "22px",
        boxSizing: "border-box",
        filter: "grayscale(80%)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "4px", flexShrink: 0 }}>
        <span style={{ fontSize: "7px", fontFamily: C.mono, color: C.muted }}>
          {vnTimeStr}
        </span>
        <span style={{ fontSize: "8px" }}>{flag}</span>
        <span style={{ fontSize: "7px", fontFamily: C.mono, color: C.muted }}>{evt.currency}</span>
      </div>

      <div style={{ fontSize: "7.5px", color: C.muted, fontFamily: C.sans, flex: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
        {evt.title}
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: "6px", flexShrink: 0, fontSize: "6.5px", fontFamily: C.mono, color: C.faint }}>
        <span>ACT: {cleanVal(evt.actual)}</span>
        <span style={{ color: C.faint, background: "rgba(255,255,255,0.03)", padding: "0 3px", borderRadius: "2px" }}>PASSED</span>
      </div>
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
  const [filterCurrency, setFilterCurrency] = useState<string>("ALL");
  const weekDays = useMemo(() => getWeekDays(), []);
  const todayIdx = useMemo(() => {
    const now = new Date();
    return now.getDay() === 0 ? 6 : now.getDay() - 1;
  }, []);

  const loadEvents = useCallback(async () => {
    try {
      const data = await fetchEconomicCalendar(7);
      if (data) setEvents(data);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadEvents();
    const interval = setInterval(loadEvents, 60000);
    return () => clearInterval(interval);
  }, [loadEvents]);

  const filteredEvents = useMemo(() => {
    return events.filter((e) => {
      const matchImpact = filterImpact === "ALL" || e.impact === filterImpact;
      const matchCurrency = filterCurrency === "ALL" || e.currency === filterCurrency;
      return matchImpact && matchCurrency;
    });
  }, [events, filterImpact, filterCurrency]);

  const dayEvents = useMemo(() => {
    if (showAllWeek) return filteredEvents;
    const day = weekDays[selectedDay];
    if (!day) return [];
    const targetM = day.getMonth() + 1;
    const targetD = day.getDate();

    return filteredEvents.filter((e) => {
      if (!e.datetime) return false;
      const d = new Date(e.datetime);
      if (isNaN(d.getTime())) return false;
      return d.getMonth() + 1 === targetM && d.getDate() === targetD;
    });
  }, [filteredEvents, selectedDay, weekDays, showAllWeek]);

  const highImpactCountsPerDay = useMemo(() => {
    return weekDays.map((d) => {
      const targetM = d.getMonth() + 1;
      const targetD = d.getDate();

      return events.filter((e) => {
        if (e.impact !== "HIGH") return false;
        if (!e.datetime) return false;
        const dt = new Date(e.datetime);
        return dt.getMonth() + 1 === targetM && dt.getDate() === targetD;
      }).length;
    });
  }, [events, weekDays]);

  const now = new Date();
  const upcoming = useMemo(() => {
    return dayEvents
      .filter((e) => e.status === "upcoming" || e.status === "live" || new Date(e.datetime) >= now)
      .sort((a, b) => new Date(a.datetime).getTime() - new Date(b.datetime).getTime());
  }, [dayEvents, now]);

  const past = useMemo(() => {
    return dayEvents
      .filter((e) => e.status === "released" || new Date(e.datetime) < now)
      .sort((a, b) => new Date(b.datetime).getTime() - new Date(a.datetime).getTime());
  }, [dayEvents, now]);

  const handleEventClick = useCallback((evt: EconomicEvent) => {
    setSelectedModalEvent(evt);
    setAnalyzing(true);
    setAnalysis(null);
    analyzeNewsEvent({
      title: evt.title,
      impact: evt.impact,
      actual: evt.actual || "",
      forecast: evt.forecast || "",
      previous: evt.previous || "",
      date: evt.datetime ? evt.datetime.slice(0, 10) : "",
      time: formatVietnamTime(evt.datetime),
    }).then((res) => {
      setAnalysis(res);
      setAnalyzing(false);
    });
    onEventSelect?.(evt);
  }, [onEventSelect]);

  const impactOptions = ["ALL", "HIGH", "MED", "LOW"];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "3px", height: "100%", minHeight: 0, background: "rgba(10, 14, 24, 0.96)", border: "1px solid rgba(255, 255, 255, 0.08)", borderRadius: "5px", padding: "4px" }}>
      {/* ── HEADER & CONTROLS ── */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
          <div style={{ width: 5, height: 5, borderRadius: "50%", background: C.greenBright, boxShadow: "0 0 6px #10b981" }} />
          <span style={{ fontSize: "8px", fontWeight: 800, color: C.text, letterSpacing: "0.05em", fontFamily: C.mono, textTransform: "uppercase" }}>
            ECONOMIC CALENDAR
          </span>
          <span style={{ fontSize: "6px", fontFamily: C.mono, color: C.cyan, background: "rgba(6,182,212,0.12)", padding: "0 3px", borderRadius: "2px", border: "1px solid rgba(6,182,212,0.25)" }}>
            GIỜ VIỆT NAM (GMT+7)
          </span>
        </div>

        <div style={{ display: "flex", gap: "2px", alignItems: "center" }}>
          {/* Toggle All Week */}
          <button
            onClick={() => setShowAllWeek(!showAllWeek)}
            style={{
              padding: "1px 4px",
              fontSize: "6.5px",
              fontFamily: C.mono,
              cursor: "pointer",
              background: showAllWeek ? "rgba(212,180,131,0.25)" : "transparent",
              border: `1px solid ${showAllWeek ? C.gold : "rgba(255,255,255,0.06)"}`,
              borderRadius: "2px",
              color: showAllWeek ? C.gold : C.muted,
              fontWeight: showAllWeek ? 800 : 500,
            }}
          >
            {showAllWeek ? "ALL WEEK" : "DAY VIEW"}
          </button>

          {/* Currency Filter */}
          <select
            value={filterCurrency}
            onChange={(e) => setFilterCurrency(e.target.value)}
            style={{
              padding: "1px 3px",
              fontSize: "6.5px",
              fontFamily: C.mono,
              background: "rgba(15, 23, 42, 0.8)",
              border: "1px solid rgba(255,255,255,0.1)",
              borderRadius: "2px",
              color: C.dim,
              outline: "none",
              cursor: "pointer",
            }}
          >
            <option value="ALL">ALL CCY</option>
            <option value="USD">🇺🇸 USD</option>
            <option value="EUR">🇪🇺 EUR</option>
            <option value="GBP">🇬🇧 GBP</option>
            <option value="JPY">🇯🇵 JPY</option>
          </select>

          {/* Impact Filter */}
          {impactOptions.map((opt) => {
            const isAct = filterImpact === opt;
            const btnColor = opt === "HIGH" ? C.red : opt === "MED" ? C.amber : opt === "LOW" ? C.muted : C.blue;
            return (
              <button
                key={opt}
                onClick={() => setFilterImpact(opt)}
                style={{
                  padding: "1px 4px",
                  fontSize: "6.5px",
                  fontFamily: C.mono,
                  cursor: "pointer",
                  background: isAct ? `rgba(${opt === "HIGH" ? "244,63,94" : opt === "MED" ? "245,158,11" : "59,130,246"}, 0.25)` : "rgba(255,255,255,0.02)",
                  border: `1px solid ${isAct ? btnColor : "rgba(255,255,255,0.06)"}`,
                  borderRadius: "2px",
                  color: isAct ? "#fff" : C.muted,
                  fontWeight: isAct ? 800 : 500,
                  transition: "all 0.15s ease",
                }}
              >
                {opt}
              </button>
            );
          })}
        </div>
      </div>

      {/* ── DAY RIBBON (T2 -> CN) ── */}
      {!showAllWeek && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: "2px", flexShrink: 0 }}>
          {weekDays.map((d, i) => {
            const isActive = i === selectedDay;
            const isToday = i === todayIdx;
            const dateStr = d.toLocaleDateString("vi-VN", { day: "numeric", month: "numeric" });
            const highCount = highImpactCountsPerDay[i] || 0;

            return (
              <button
                key={`day-${i}`}
                onClick={() => setSelectedDay(i)}
                style={{
                  height: "18px",
                  padding: "0 2px",
                  background: isActive ? "rgba(212, 180, 131, 0.2)" : isToday ? "rgba(255,255,255,0.04)" : "rgba(255,255,255,0.02)",
                  border: `1px solid ${isActive ? C.gold : isToday ? "rgba(212,180,131,0.4)" : "rgba(255,255,255,0.05)"}`,
                  borderRadius: "3px",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "2px",
                  transition: "all 0.15s ease",
                  position: "relative",
                }}
              >
                <span style={{ fontSize: "6.5px", color: isActive ? C.gold : C.muted, fontFamily: C.mono, fontWeight: 700 }}>
                  {["T2", "T3", "T4", "T5", "T6", "T7", "CN"][i]}
                </span>
                <span style={{ fontSize: "7px", color: isActive ? "#fff" : C.dim, fontFamily: C.mono, fontWeight: isActive ? 800 : 500 }}>
                  {dateStr}
                </span>

                {/* High impact badge indicator */}
                {highCount > 0 && (
                  <div style={{ position: "absolute", top: -2, right: -2, background: C.red, color: "#fff", fontSize: "5px", fontFamily: C.mono, fontWeight: 900, width: "9px", height: "9px", borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", boxShadow: "0 0 4px #f43f5e" }}>
                    {highCount}
                  </div>
                )}
              </button>
            );
          })}
        </div>
      )}

      <div style={{ height: "1px", background: "rgba(255,255,255,0.06)", flexShrink: 0 }} />

      {/* ── EVENT LIST (SCROLLABLE DENSE TABLE) ── */}
      <div style={{ flex: 1, overflowY: "auto", minHeight: 0, display: "flex", flexDirection: "column", gap: "2px", paddingRight: "1px" }}>
        {loading ? (
          <>
            <SkeletonRow />
            <SkeletonRow />
            <SkeletonRow />
          </>
        ) : upcoming.length === 0 && past.length === 0 ? (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", color: C.muted, fontFamily: C.mono, fontSize: "8px", gap: "4px" }}>
            <span>📅 Không có tin kinh tế nào trong ngày này.</span>
            <button
              onClick={() => setShowAllWeek(true)}
              style={{
                padding: "3px 8px",
                fontSize: "7.5px",
                fontFamily: C.mono,
                background: "rgba(212, 180, 131, 0.2)",
                border: "1px solid #D4B483",
                borderRadius: "3px",
                color: C.gold,
                fontWeight: 700,
                cursor: "pointer",
                marginTop: "4px",
              }}
            >
              [XEM TẤT CẢ TIN TRONG TUẦN]
            </button>
          </div>
        ) : (
          <>
            {/* 1. UPCOMING EVENTS HIGHLIGHTED AT THE TOP */}
            {upcoming.length > 0 && (
              <div>
                <div style={{ fontSize: "7px", fontFamily: C.mono, color: C.cyan, fontWeight: 900, letterSpacing: "0.06em", marginBottom: "3px", textTransform: "uppercase", display: "flex", alignItems: "center", gap: "4px" }}>
                  <span style={{ width: 6, height: 6, background: C.cyan, borderRadius: "50%", boxShadow: "0 0 8px #06b6d4" }} />
                  🔥 UPCOMING EVENTS (GIỜ VN GMT+7) ({upcoming.length})
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
                  {upcoming.map((evt, idx) => (
                    <UpcomingEventRow key={`${evt.id}-${evt.datetime}-${idx}`} evt={evt} onClick={handleEventClick} />
                  ))}
                </div>
              </div>
            )}

            {/* 2. PASSED EVENTS DIMMED AT THE BOTTOM */}
            {past.length > 0 && (
              <div>
                <div style={{ fontSize: "6.5px", fontFamily: C.mono, color: C.muted, fontWeight: 700, letterSpacing: "0.05em", marginBottom: "2px", textTransform: "uppercase", marginTop: upcoming.length > 0 ? "6px" : 0 }}>
                  🔒 RELEASED / PASSED EVENTS ({past.length})
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
                  {past.map((evt, idx) => (
                    <PastEventRow key={`${evt.id}-${evt.datetime}-${idx}`} evt={evt} />
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* ── MODAL: AI EVENT TRADE ASSESSMENT & RECOMMENDATION BOX ── */}
      {selectedModalEvent && (
        <div
          onClick={() => setSelectedModalEvent(null)}
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(5, 7, 12, 0.85)",
            backdropFilter: "blur(12px)",
            WebkitBackdropFilter: "blur(12px)",
            zIndex: 99999,
            display: "grid",
            placeItems: "center",
            padding: "16px",
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: "linear-gradient(135deg, rgba(10, 14, 24, 0.98), rgba(15, 23, 42, 0.98))",
              border: "1px solid rgba(212, 180, 131, 0.4)",
              borderRadius: "8px",
              width: "100%",
              maxWidth: "580px",
              padding: "16px 20px",
              boxShadow: "0 12px 48px rgba(0, 0, 0, 0.85), 0 0 30px rgba(6, 182, 212, 0.25)",
              color: C.text,
            }}
          >
            {/* Modal Header */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px", borderBottom: "1px solid rgba(255,255,255,0.08)", paddingBottom: "8px" }}>
              <div>
                <div style={{ fontSize: "11px", fontWeight: 800, color: C.gold, fontFamily: C.mono, letterSpacing: "0.05em" }}>
                  🤖 AI COPILOT MACRO NEWS ASSESSMENT
                </div>
                <div style={{ fontSize: "8.5px", color: C.muted, fontFamily: C.sans, marginTop: "1px" }}>
                  Đánh giá tác động tin tức kinh tế & Khuyến nghị vị thế Gold (XAUUSD)
                </div>
              </div>
              <button
                onClick={() => setSelectedModalEvent(null)}
                style={{
                  background: "rgba(255,255,255,0.06)",
                  border: "1px solid rgba(255,255,255,0.1)",
                  borderRadius: "4px",
                  color: C.muted,
                  fontSize: "11px",
                  width: "24px",
                  height: "24px",
                  cursor: "pointer",
                  display: "grid",
                  placeItems: "center",
                }}
              >
                ✕
              </button>
            </div>

            {/* Event Info Card */}
            <div style={{ background: "rgba(0,0,0,0.4)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: "5px", padding: "8px 12px", marginBottom: "12px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                <div style={{ fontSize: "10.5px", fontWeight: 700, color: C.text, fontFamily: C.sans }}>
                  {countryFlags[selectedModalEvent.currency] || "🌐"} {selectedModalEvent.title}
                </div>
                <span style={{ fontSize: "7.5px", fontFamily: C.mono, fontWeight: 900, color: selectedModalEvent.impact === "HIGH" ? C.red : C.amber, background: selectedModalEvent.impact === "HIGH" ? "rgba(244,63,94,0.2)" : "rgba(245,158,11,0.2)", padding: "1px 6px", borderRadius: "3px", border: `1px solid ${selectedModalEvent.impact === "HIGH" ? C.red : C.amber}` }}>
                  {selectedModalEvent.impact} IMPACT
                </span>
              </div>
              <div style={{ display: "flex", gap: "12px", fontSize: "8px", fontFamily: C.mono, color: C.muted }}>
                <span>Release Time (Giờ VN): <strong style={{ color: C.cyan }}>{formatVietnamTime(selectedModalEvent.datetime)}</strong></span>
                <span>Forecast: <strong style={{ color: C.gold }}>{cleanVal(selectedModalEvent.forecast)}</strong></span>
                <span>Previous: <strong style={{ color: C.dim }}>{cleanVal(selectedModalEvent.previous)}</strong></span>
              </div>
            </div>

            {/* AI Recommendation Badge */}
            {analyzing ? (
              <div style={{ textAlign: "center", padding: "16px", color: C.cyan, fontFamily: C.mono, fontSize: "9px" }}>
                🤖 AI COPILOT đang phân tích tác động vĩ mô và kỹ thuật cho XAUUSD...
              </div>
            ) : (
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "12px", background: "rgba(15, 23, 42, 0.8)", border: "1px solid rgba(255,255,255,0.08)", padding: "8px 12px", borderRadius: "5px" }}>
                  <span style={{ fontSize: "9px", fontFamily: C.mono, color: C.muted }}>Khuyến nghị AI:</span>
                  <span
                    style={{
                      fontSize: "12px",
                      fontFamily: C.mono,
                      fontWeight: 900,
                      letterSpacing: "0.06em",
                      padding: "2px 10px",
                      borderRadius: "4px",
                      background: analysis?.recommendation === "BUY" ? "rgba(16, 185, 129, 0.25)" : analysis?.recommendation === "SELL" ? "rgba(244, 63, 94, 0.25)" : "rgba(245, 158, 11, 0.25)",
                      color: analysis?.recommendation === "BUY" ? C.greenBright : analysis?.recommendation === "SELL" ? C.red : C.amber,
                      border: `1px solid ${analysis?.recommendation === "BUY" ? C.greenBright : analysis?.recommendation === "SELL" ? C.red : C.amber}`,
                      boxShadow: `0 0 10px ${analysis?.recommendation === "BUY" ? "rgba(16, 185, 129, 0.3)" : analysis?.recommendation === "SELL" ? "rgba(244, 63, 94, 0.3)" : "rgba(245, 158, 11, 0.3)"}`,
                    }}
                  >
                    {analysis?.recommendation === "BUY" ? "BUY MARKET (MUA XAUUSD)" : analysis?.recommendation === "SELL" ? "SELL MARKET (BÁN XAUUSD)" : "NEUTRAL / KHÔNG VÀO LỆNH"}
                  </span>
                </div>

                {/* AI Analysis Text */}
                <div style={{ fontSize: "8.5px", fontFamily: C.sans, color: C.dim, lineHeight: 1.5, background: "rgba(0, 0, 0, 0.5)", border: "1px solid rgba(255,255,255,0.06)", padding: "10px 12px", borderRadius: "5px", maxHeight: "220px", overflowY: "auto", whiteSpace: "pre-wrap" }}>
                  {analysis?.analysis || "AI Copilot đã hoàn tất đánh giá rủi ro."}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}