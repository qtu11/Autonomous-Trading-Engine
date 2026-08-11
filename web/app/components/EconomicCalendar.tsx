'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import { fetchEconomicCalendar, analyzeNewsEvent, type EconomicEvent, type NewsAnalysisResponse } from '../../lib/api';

const C = {
  gold: '#D4B483',
  goldDim: 'rgba(212,175,55,0.12)',
  green: '#22d3a0',
  greenDim: 'rgba(34,211,160,0.12)',
  red: '#f43f5e',
  redDim: 'rgba(244,63,94,0.12)',
  cyan: '#06b6d4',
  text: '#f8fafc',
  dim: '#cbd5e1',
  muted: '#64748b',
  border: 'rgba(255,255,255,0.06)',
  mono: '"JetBrains Mono", monospace',
  sans: '"Inter", -apple-system, sans-serif',
};

const impactColors = {
  HIGH: { bg: 'rgba(244,63,94,0.15)', text: '#f43f5e', border: 'rgba(244,63,94,0.4)' },
  MED: { bg: 'rgba(245,158,11,0.15)', text: '#f59e0b', border: 'rgba(245,158,11,0.4)' },
  LOW: { bg: 'rgba(100,116,139,0.1)', text: '#94a3b8', border: 'rgba(100,116,139,0.25)' },
};

function cleanVal(val?: string | null): string {
  if (!val || val === 'N/A' || val === 'N' || val === 'None' || val.trim() === '') return '--';
  return val.trim();
}

function formatTime(isoStr: string): string {
  if (!isoStr) return '12:00';
  try {
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) return isoStr.slice(11, 16);
    return d.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Asia/Ho_Chi_Minh' });
  } catch { return isoStr.slice(11, 16); }
}

function formatCountdown(target: Date): string {
  const diff = target.getTime() - Date.now();
  if (diff <= 0) return 'LIVE';
  const h = Math.floor(diff / 3600000);
  const m = Math.floor((diff % 3600000) / 60000);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function getWeekDays(): Date[] {
  const now = new Date();
  const monday = new Date(now);
  monday.setDate(now.getDate() - (now.getDay() === 0 ? 6 : now.getDay() - 1));
  monday.setHours(0, 0, 0, 0);
  return Array.from({ length: 7 }, (_, i) => { const d = new Date(monday); d.setDate(monday.getDate() + i); return d; });
}

function EventRow({ evt, onClick }: { evt: EconomicEvent; onClick: (e: EconomicEvent) => void }) {
  const ic = impactColors[evt.impact?.toUpperCase() as keyof typeof impactColors] || impactColors.LOW;
  const evtTime = new Date(evt.datetime);

  return (
    <div onClick={() => onClick(evt)} style={{
      padding: '5px 8px',
      background: `linear-gradient(90deg, rgba(6,182,212,0.08) 0%, rgba(5,7,12,0.9) 100%)`,
      borderLeft: `3px solid ${ic.text}`,
      border: `1px solid ${ic.border}`,
      borderRadius: 4, cursor: 'pointer', marginBottom: 3, display: 'flex', alignItems: 'center', gap: 8,
    }}>
      <span style={{ fontSize: 8, fontFamily: C.mono, color: C.text, fontWeight: 700, background: 'rgba(0,0,0,0.4)', padding: '2px 5px', borderRadius: 3 }}>
        {formatTime(evt.datetime)}
      </span>
      <span style={{ fontSize: 7, fontFamily: C.mono, color: C.gold, fontWeight: 800 }}>{evt.currency}</span>
      <span style={{ fontSize: 8, color: C.dim, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{evt.title}</span>
      <span style={{ fontSize: 7, fontFamily: C.mono, color: C.muted }}>FC: <strong style={{ color: C.gold }}>{cleanVal(evt.forecast)}</strong></span>
      <div style={{ padding: '2px 6px', background: 'rgba(6,182,212,0.15)', border: '1px solid #06b6d4', borderRadius: 3 }}>
        <span style={{ fontSize: 7, fontFamily: C.mono, fontWeight: 800, color: C.cyan }}>{formatCountdown(evtTime)}</span>
      </div>
    </div>
  );
}

export default function EconomicCalendar() {
  const [events, setEvents] = useState<EconomicEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedDay, setSelectedDay] = useState<number>(new Date().getDay() === 0 ? 6 : new Date().getDay() - 1);
  const [filterImpact, setFilterImpact] = useState<string>('ALL');
  const [selectedEvent, setSelectedEvent] = useState<EconomicEvent | null>(null);
  const [analysis, setAnalysis] = useState<NewsAnalysisResponse | null>(null);
  const [analyzing, setAnalyzing] = useState(false);

  const weekDays = useMemo(() => getWeekDays(), []);
  const todayIdx = useMemo(() => { const now = new Date(); return now.getDay() === 0 ? 6 : now.getDay() - 1; }, []);

  const loadEvents = useCallback(async () => {
    try {
      const data = await fetchEconomicCalendar(7);
      if (data) setEvents(data);
    } catch { /* silent */ } finally { setLoading(false); }
  }, []);

  useEffect(() => { loadEvents(); const interval = setInterval(loadEvents, 60000); return () => clearInterval(interval); }, [loadEvents]);

  const filteredEvents = useMemo(() => events.filter(e => filterImpact === 'ALL' || e.impact?.toUpperCase() === filterImpact), [events, filterImpact]);

  const dayEvents = useMemo(() => {
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
  }, [filteredEvents, selectedDay, weekDays]);

  const now = new Date();
  const upcoming = useMemo(() => dayEvents.filter(e => new Date(e.datetime) >= now).sort((a, b) => new Date(a.datetime).getTime() - new Date(b.datetime).getTime()), [dayEvents, now]);

  const handleEventClick = useCallback((evt: EconomicEvent) => {
    setSelectedEvent(evt);
    setAnalyzing(true);
    setAnalysis(null);
    analyzeNewsEvent({ title: evt.title, impact: evt.impact, actual: evt.actual || '', forecast: evt.forecast || '', previous: evt.previous || '', date: evt.datetime?.slice(0, 10) || '', time: formatTime(evt.datetime) })
      .then(res => { setAnalysis(res); setAnalyzing(false); });
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, height: '100%', minHeight: 0, background: 'rgba(5,7,12,0.95)', borderRadius: 6, padding: 6 }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ width: 6, height: 6, borderRadius: '50%', background: C.green, boxShadow: `0 0 8px ${C.green}` }} />
          <span style={{ fontSize: 8, fontWeight: 800, color: C.text, fontFamily: C.mono }}>ECONOMIC CALENDAR</span>
        </div>
        <div style={{ display: 'flex', gap: 3 }}>
          {['ALL', 'HIGH', 'MED', 'LOW'].map(opt => {
            const isAct = filterImpact === opt;
            const btnColor = opt === 'HIGH' ? C.red : opt === 'MED' ? '#f59e0b' : C.muted;
            return (
              <button key={opt} onClick={() => setFilterImpact(opt)} style={{
                padding: '2px 5px', fontSize: 7, fontFamily: C.mono, cursor: 'pointer',
                background: isAct ? `rgba(${opt === 'HIGH' ? '244,63,94' : opt === 'MED' ? '245,158,11' : '59,130,246'}, 0.2)` : 'transparent',
                border: `1px solid ${isAct ? btnColor : C.border}`, borderRadius: 3, color: isAct ? '#fff' : C.muted, fontWeight: isAct ? 800 : 500,
              }}>{opt}</button>
            );
          })}
        </div>
      </div>

      {/* Day Ribbon */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 3, flexShrink: 0 }}>
        {weekDays.map((d, i) => {
          const isActive = i === selectedDay;
          const dateStr = d.toLocaleDateString('vi-VN', { day: 'numeric', month: 'numeric' });
          return (
            <button key={`day-${i}`} onClick={() => setSelectedDay(i)} style={{
              height: 20, padding: '0 3px', background: isActive ? C.goldDim : 'transparent',
              border: `1px solid ${isActive ? C.gold : C.border}`, borderRadius: 4, cursor: 'pointer',
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 1,
            }}>
              <span style={{ fontSize: 7, color: isActive ? C.gold : C.muted, fontFamily: C.mono, fontWeight: 700 }}>{['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN'][i]}</span>
              <span style={{ fontSize: 7, color: isActive ? '#fff' : C.dim, fontFamily: C.mono }}>{dateStr}</span>
            </button>
          );
        })}
      </div>

      <div style={{ height: 1, background: 'rgba(255,255,255,0.05)' }} />

      {/* Event List */}
      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 2 }}>
        {loading ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: C.muted, fontFamily: C.mono, fontSize: 8 }}>LOADING...</div>
        ) : upcoming.length === 0 ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: C.muted, fontFamily: C.mono, fontSize: 8 }}>No events</div>
        ) : (
          upcoming.map((evt, idx) => <EventRow key={`${evt.id}-${idx}`} evt={evt} onClick={handleEventClick} />)
        )}
      </div>

      {/* Modal */}
      {selectedEvent && (
        <div onClick={() => setSelectedEvent(null)} style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(2,3,5,0.9)', backdropFilter: 'blur(16px)', zIndex: 99999,
          display: 'grid', placeItems: 'center', padding: 20,
        }}>
          <div onClick={e => e.stopPropagation()} style={{
            background: 'rgba(8,12,22,0.98)', borderRadius: 12, width: '100%', maxWidth: 480,
            padding: '20px 24px', border: '1px solid rgba(212,175,55,0.3)',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16, paddingBottom: 12, borderBottom: `1px solid ${C.border}` }}>
              <div>
                <div style={{ fontSize: 10, fontWeight: 800, color: C.gold, fontFamily: C.mono }}>AI MACRO ASSESSMENT</div>
                <div style={{ fontSize: 8, color: C.muted }}>{selectedEvent.currency} {selectedEvent.title}</div>
              </div>
              <button onClick={() => setSelectedEvent(null)} style={{
                background: 'rgba(255,255,255,0.05)', border: `1px solid ${C.border}`, borderRadius: 4,
                color: C.muted, fontSize: 12, width: 28, height: 28, cursor: 'pointer',
              }}>X</button>
            </div>

            <div style={{ background: 'rgba(0,0,0,0.4)', borderRadius: 6, padding: '10px 14px', marginBottom: 14 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <span style={{ fontSize: 9, fontWeight: 700, color: C.text }}>{selectedEvent.title}</span>
                <span style={{ fontSize: 7, fontFamily: C.mono, fontWeight: 900, color: impactColors[selectedEvent.impact?.toUpperCase() as keyof typeof impactColors]?.text || C.muted, background: impactColors[selectedEvent.impact?.toUpperCase() as keyof typeof impactColors]?.bg, padding: '2px 8px', borderRadius: 3 }}>
                  {selectedEvent.impact}
                </span>
              </div>
              <div style={{ display: 'flex', gap: 16, fontSize: 8, fontFamily: C.mono, color: C.muted }}>
                <span>Time: <strong style={{ color: C.cyan }}>{formatTime(selectedEvent.datetime)}</strong></span>
                <span>Forecast: <strong style={{ color: C.gold }}>{cleanVal(selectedEvent.forecast)}</strong></span>
                <span>Previous: <strong style={{ color: C.dim }}>{cleanVal(selectedEvent.previous)}</strong></span>
              </div>
            </div>

            {analyzing ? (
              <div style={{ textAlign: 'center', padding: 20, color: C.cyan, fontFamily: C.mono, fontSize: 9 }}>
                AI analyzing...
              </div>
            ) : analysis ? (
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
                  <span style={{ fontSize: 8, fontFamily: C.mono, color: C.muted }}>Recommendation:</span>
                  <span style={{
                    fontSize: 11, fontFamily: C.mono, fontWeight: 900,
                    padding: '3px 12px', borderRadius: 4,
                    background: analysis.recommendation === 'BUY' ? C.greenDim : analysis.recommendation === 'SELL' ? C.redDim : C.goldDim,
                    color: analysis.recommendation === 'BUY' ? C.green : analysis.recommendation === 'SELL' ? C.red : C.gold,
                    border: `1px solid ${analysis.recommendation === 'BUY' ? C.green : analysis.recommendation === 'SELL' ? C.red : C.gold}`,
                  }}>
                    {analysis.recommendation}
                  </span>
                </div>
                <div style={{ fontSize: 8.5, fontFamily: C.sans, color: C.dim, lineHeight: 1.6, background: 'rgba(0,0,0,0.4)', padding: '12px 14px', borderRadius: 6, maxHeight: 150, overflowY: 'auto' }}>
                  {analysis.analysis}
                </div>
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
