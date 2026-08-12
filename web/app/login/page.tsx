'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';

const API_BASE = '';

const TICKER_ITEMS = [
  { symbol: 'XAU/USD', price: '2,845.50', change: '+1.24%', isUp: true },
  { symbol: 'SPX 500', price: '5,980.20', change: '+0.45%', isUp: true },
  { symbol: 'NASDAQ 100', price: '21,450.80', change: '+0.82%', isUp: true },
  { symbol: 'BTC/USD', price: '98,400.00', change: '-0.35%', isUp: false },
  { symbol: 'EUR/USD', price: '1.0845', change: '+0.12%', isUp: true },
  { symbol: '10Y YIELD', price: '4.28%', change: '-0.04%', isUp: false },
];

const C = {
  bg: '#020305',
  bgDark: '#010102',
  gold: '#D4B483',
  goldBright: '#F0D5A0',
  goldDim: 'rgba(212,175,55,0.15)',
  green: '#22d3a0',
  red: '#f43f5e',
  blue: '#38bdf8',
  text: '#f8fafc',
  dim: '#cbd5e1',
  muted: '#64748b',
  faint: '#475569',
  mono: '"JetBrains Mono", monospace',
  sans: '"Inter", -apple-system, BlinkMacSystemFont, sans-serif',
};

export default function LoginPage() {
  const router = useRouter();
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  const cardRef = useRef<HTMLDivElement>(null);
  const [tilt, setTilt] = useState({ rotateX: 0, rotateY: 0 });
  const [glare, setGlare] = useState({ x: 50, y: 50, opacity: 0 });

  useEffect(() => {
    const token = localStorage.getItem('quantai_auth_token');
    if (token) router.push('/');
  }, [router]);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!cardRef.current) return;
    const rect = cardRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const cx = rect.width / 2;
    const cy = rect.height / 2;
    const rx = ((y - cy) / cy) * -8;
    const ry = ((x - cx) / cx) * 8;
    setTilt({ rotateX: rx, rotateY: ry });
    setGlare({ x: (x / rect.width) * 100, y: (y / rect.height) * 100, opacity: 0.12 });
  };

  const handleMouseLeave = () => {
    setTilt({ rotateX: 0, rotateY: 0 });
    setGlare({ x: 50, y: 50, opacity: 0 });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg('');
    setSuccessMsg('');

    if (!login.trim() || !password.trim()) {
      setErrorMsg('Vui long nhap day du thong tin dang nhap');
      return;
    }

    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ login: login.trim(), password: password.trim() }),
      });

      const data = await res.json();

      if (res.ok && data.status === 'SUCCESS') {
        setSuccessMsg('Xac thuc thanh cong. Dang truy cap...');
        const token = data.access_token || data.token || 'authenticated';
        localStorage.setItem('quantai_auth_token', token);
        localStorage.setItem('quantai_user_info', JSON.stringify(data.user || {}));
        document.cookie = `access_token=${token}; path=/; max-age=604800; SameSite=Lax`;
        document.cookie = `quantai_auth=${token}; path=/; max-age=604800; SameSite=Lax`;
        setTimeout(() => router.push('/'), 800);
      } else {

        setErrorMsg(data.detail?.message || data.detail?.code || 'Xac thuc that bai');
      }
    } catch {
      setErrorMsg('Khong the ket noi backend. Vui long kiem tra dich vu.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      background: `
        radial-gradient(ellipse at 50% 0%, rgba(212,175,55,0.08) 0%, transparent 50%),
        radial-gradient(ellipse at 15% 60%, rgba(16,185,129,0.04) 0%, transparent 40%),
        radial-gradient(ellipse at 85% 40%, rgba(59,130,246,0.03) 0%, transparent 45%),
        linear-gradient(180deg, #020305 0%, #010102 100%)
      `,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      fontFamily: C.sans,
      padding: '60px 20px 20px',
      position: 'relative',
      overflow: 'hidden',
    }}>
      {/* ── FINANCIAL TICKER BAR ── */}
      <div style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        height: 40,
        background: 'linear-gradient(180deg, rgba(5,8,14,0.98) 0%, rgba(3,5,8,0.95) 100%)',
        borderBottom: '1px solid rgba(212,175,55,0.2)',
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
        zIndex: 100,
        display: 'flex',
        alignItems: 'center',
        overflow: 'hidden',
        boxShadow: '0 4px 24px rgba(0,0,0,0.6)',
      }}>
        <div style={{
          background: 'linear-gradient(135deg, #d4af37, #996515)',
          color: '#000',
          padding: '0 16px',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          fontWeight: 900,
          fontSize: 9,
          letterSpacing: '1.5px',
          fontFamily: C.mono,
          flexShrink: 0,
          boxShadow: '4px 0 16px rgba(0,0,0,0.5)',
        }}>
          MARKETS
        </div>
        <div className="animate-marquee" style={{ display: 'flex', gap: 40, paddingLeft: 24 }}>
          {[...TICKER_ITEMS, ...TICKER_ITEMS].map((item, idx) => (
            <div key={idx} style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              fontSize: 11,
              fontFamily: C.mono,
            }}>
              <span style={{ color: '#94a3b8', fontWeight: 600 }}>{item.symbol}</span>
              <span style={{ color: '#fff', fontWeight: 700 }}>{item.price}</span>
              <span style={{
                color: item.isUp ? C.green : C.red,
                fontWeight: 700,
                fontSize: 10,
                background: item.isUp ? 'rgba(34,211,160,0.1)' : 'rgba(244,63,94,0.1)',
                padding: '2px 8px',
                borderRadius: 4,
              }}>
                {item.change}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* ── BACKGROUND DECORATIVE ELEMENTS ── */}
      <div style={{
        position: 'absolute',
        inset: 0,
        pointerEvents: 'none',
        overflow: 'hidden',
      }}>
        {/* Left Candlestick Graphic */}
        <svg
          style={{ position: 'absolute', left: '5%', top: '50%', transform: 'translateY(-50%)', opacity: 0.08 }}
          width="280" height="380" viewBox="0 0 280 380"
        >
          <defs>
            <linearGradient id="goldLine" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#D4B483" stopOpacity="0.6" />
              <stop offset="100%" stopColor="#D4B483" stopOpacity="0.1" />
            </linearGradient>
            <linearGradient id="greenGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#22d3a0" stopOpacity="0.3" />
              <stop offset="100%" stopColor="#22d3a0" stopOpacity="0" />
            </linearGradient>
          </defs>
          <line x1="30" y1="40" x2="30" y2="340" stroke="#10b981" strokeWidth="1" strokeDasharray="4 4" />
          <line x1="100" y1="40" x2="100" y2="340" stroke="#ef4444" strokeWidth="1" strokeDasharray="4 4" />
          <line x1="170" y1="40" x2="170" y2="340" stroke="#d4af37" strokeWidth="1" strokeDasharray="4 4" />
          <line x1="240" y1="40" x2="240" y2="340" stroke="#38bdf8" strokeWidth="1" strokeDasharray="4 4" />
          <line x1="50" y1="60" x2="50" y2="260" stroke="#10b981" strokeWidth="2" />
          <rect x="38" y="100" width="24" height="120" fill="url(#greenGrad)" rx="2" />
          <line x1="120" y1="50" x2="120" y2="300" stroke="#ef4444" strokeWidth="2" />
          <rect x="108" y="90" width="24" height="160" fill="#ef4444" opacity="0.3" rx="2" />
          <line x1="190" y1="30" x2="190" y2="350" stroke="url(#goldLine)" strokeWidth="2" />
          <rect x="178" y="60" width="24" height="220" fill="#d4af37" opacity="0.2" rx="2" />
        </svg>

        {/* Right Area Chart */}
        <svg
          style={{ position: 'absolute', right: '5%', top: '50%', transform: 'translateY(-50%)', opacity: 0.08 }}
          width="280" height="380" viewBox="0 0 280 380"
        >
          <defs>
            <linearGradient id="areaGreen" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#22d3a0" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#22d3a0" stopOpacity="0" />
            </linearGradient>
          </defs>
          <path d="M0 350 Q60 280, 120 200 T280 40" fill="none" stroke="#22d3a0" strokeWidth="2" />
          <path d="M0 350 Q60 280, 120 200 T280 40 L280 380 L0 380 Z" fill="url(#areaGreen)" />
          <path d="M0 50 Q80 150, 160 220 T280 360" fill="none" stroke="#f43f5e" strokeWidth="1.5" strokeDasharray="5 5" opacity="0.6" />
        </svg>

        {/* Grid Pattern Overlay */}
        <div style={{
          position: 'absolute',
          inset: 0,
          backgroundImage: `
            linear-gradient(rgba(255,255,255,0.015) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255,255,255,0.015) 1px, transparent 1px)
          `,
          backgroundSize: '60px 60px',
          opacity: 0.5,
        }} />
      </div>

      {/* ── MAIN LOGIN CARD ── */}
      <div
        ref={cardRef}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        className="gradient-border"
        style={{
          width: '100%',
          maxWidth: 440,
          background: 'linear-gradient(145deg, rgba(8,12,22,0.92) 0%, rgba(3,5,8,0.98) 100%)',
          backdropFilter: 'blur(40px)',
          WebkitBackdropFilter: 'blur(40px)',
          borderRadius: 20,
          boxShadow: `
            0 40px 120px rgba(0,0,0,0.9),
            0 0 80px rgba(212,175,55,0.08),
            inset 0 1px 1px rgba(255,255,255,0.08)
          `,
          padding: '40px 36px',
          position: 'relative',
          zIndex: 10,
          transform: `perspective(1200px) rotateX(${tilt.rotateX}deg) rotateY(${tilt.rotateY}deg) scale3d(1,1,1)`,
          transition: 'transform 0.12s ease-out',
        }}
      >
        {/* Dynamic Glare */}
        <div style={{
          position: 'absolute',
          inset: 0,
          borderRadius: 20,
          background: `radial-gradient(circle at ${glare.x}% ${glare.y}%, rgba(255,255,255,${glare.opacity}), transparent 55%)`,
          pointerEvents: 'none',
          transition: 'opacity 0.2s ease',
        }} />

        {/* Header */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 28,
          paddingBottom: 20,
          borderBottom: '1px solid rgba(255,255,255,0.05)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{
              width: 10,
              height: 10,
              borderRadius: '50%',
              background: C.green,
              boxShadow: `0 0 12px ${C.green}`,
            }} />
            <span style={{
              fontSize: 9,
              fontFamily: C.mono,
              color: C.gold,
              fontWeight: 800,
              letterSpacing: '1.5px',
            }}>
              ATE FINANCIAL DESK
            </span>
          </div>
          <div style={{
            fontSize: 8,
            fontFamily: C.mono,
            color: C.muted,
            background: 'rgba(255,255,255,0.03)',
            padding: '4px 10px',
            borderRadius: 6,
            border: '1px solid rgba(255,255,255,0.05)',
          }}>
            SECURE SESSION
          </div>
        </div>

        {/* Brand Logo */}
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 72,
            height: 72,
            borderRadius: 18,
            background: 'linear-gradient(145deg, rgba(212,175,55,0.25) 0%, rgba(5,7,12,0.9) 100%)',
            border: '1px solid rgba(212,175,55,0.45)',
            marginBottom: 18,
            boxShadow: `
              0 16px 40px rgba(0,0,0,0.7),
              0 0 40px rgba(212,175,55,0.2),
              inset 0 1px 1px rgba(255,255,255,0.1)
            `,
          }}>
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke={C.gold} strokeWidth="1.5">
              <path d="M12 2L2 7l10 5 10-5-10-5z" />
              <path d="M2 17l10 5 10-5" />
              <path d="M2 12l10 5 10-5" />
            </svg>
          </div>

          <h1 style={{
            color: '#fff',
            fontSize: 16,
            fontWeight: 900,
            letterSpacing: '3px',
            margin: '0 0 8px 0',
            textTransform: 'uppercase',
            fontFamily: C.mono,
          }}>
            AUTONOMOUS <span style={{ color: C.gold }}>TRADING</span> ENGINE
          </h1>
          <p style={{
            color: C.muted,
            fontSize: 9,
            margin: 0,
            letterSpacing: '2px',
            fontWeight: 700,
            textTransform: 'uppercase',
          }}>
            Institutional Terminal — QTusdev
          </p>
        </div>

        {/* System Metrics */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: 8,
          background: 'rgba(0,0,0,0.4)',
          border: '1px solid rgba(212,175,55,0.1)',
          borderRadius: 12,
          padding: 14,
          marginBottom: 28,
          fontSize: 9,
          fontFamily: C.mono,
        }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ color: C.muted, fontSize: 7, marginBottom: 3 }}>GATEWAY</div>
            <div style={{ color: C.blue, fontWeight: 800 }}>MULTI_AI</div>
          </div>
          <div style={{ textAlign: 'center', borderLeft: '1px solid rgba(255,255,255,0.05)', borderRight: '1px solid rgba(255,255,255,0.05)' }}>
            <div style={{ color: C.muted, fontSize: 7, marginBottom: 3 }}>RISK</div>
            <div style={{ color: C.gold, fontWeight: 800 }}>1.0% MAX</div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ color: C.muted, fontSize: 7, marginBottom: 3 }}>ENGINE</div>
            <div style={{ color: C.green, fontWeight: 800 }}>MT5</div>
          </div>
        </div>

        {/* Alerts */}
        {errorMsg && (
          <div style={{
            background: 'rgba(244,63,94,0.08)',
            border: '1px solid rgba(244,63,94,0.35)',
            borderRadius: 10,
            padding: '12px 16px',
            color: '#f87171',
            fontSize: 11,
            fontWeight: 600,
            marginBottom: 20,
            fontFamily: C.mono,
          }}>
            {errorMsg}
          </div>
        )}

        {successMsg && (
          <div style={{
            background: 'rgba(34,211,160,0.08)',
            border: '1px solid rgba(34,211,160,0.35)',
            borderRadius: 10,
            padding: '12px 16px',
            color: '#6ee7b7',
            fontSize: 11,
            fontWeight: 600,
            marginBottom: 20,
            fontFamily: C.mono,
          }}>
            {successMsg}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <div>
            <label style={{
              display: 'block',
              color: C.dim,
              fontSize: 10,
              fontWeight: 800,
              letterSpacing: '1px',
              marginBottom: 10,
              textTransform: 'uppercase',
              fontFamily: C.mono,
            }}>
              Operator ID / Email
            </label>
            <input
              type="text"
              value={login}
              onChange={(e) => setLogin(e.target.value)}
              placeholder="Nhap thong tin dang nhap..."
              required
              style={{
                width: '100%',
                padding: '14px 16px',
                background: 'rgba(0,0,0,0.5)',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: 10,
                color: '#fff',
                fontSize: 13,
                fontFamily: C.mono,
                outline: 'none',
                transition: 'all 0.25s ease',
                boxSizing: 'border-box',
              }}
              onFocus={(e) => {
                e.target.style.borderColor = C.gold;
                e.target.style.boxShadow = `0 0 24px ${C.goldDim}`;
              }}
              onBlur={(e) => {
                e.target.style.borderColor = 'rgba(255,255,255,0.08)';
                e.target.style.boxShadow = 'none';
              }}
            />
          </div>

          <div>
            <label style={{
              display: 'block',
              color: C.dim,
              fontSize: 10,
              fontWeight: 800,
              letterSpacing: '1px',
              marginBottom: 10,
              textTransform: 'uppercase',
              fontFamily: C.mono,
            }}>
              Access Code
            </label>
            <div style={{ position: 'relative' }}>
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Nhap mat khau..."
                required
                style={{
                  width: '100%',
                  padding: '14px 48px 14px 16px',
                  background: 'rgba(0,0,0,0.5)',
                  border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: 10,
                  color: '#fff',
                  fontSize: 13,
                  fontFamily: C.mono,
                  outline: 'none',
                  transition: 'all 0.25s ease',
                  boxSizing: 'border-box',
                }}
                onFocus={(e) => {
                  e.target.style.borderColor = C.gold;
                  e.target.style.boxShadow = `0 0 24px ${C.goldDim}`;
                }}
                onBlur={(e) => {
                  e.target.style.borderColor = 'rgba(255,255,255,0.08)';
                  e.target.style.boxShadow = 'none';
                }}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                style={{
                  position: 'absolute',
                  right: 14,
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none',
                  border: 'none',
                  color: showPassword ? C.gold : C.muted,
                  cursor: 'pointer',
                  padding: 0,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  transition: 'color 0.2s ease',
                }}
              >
                {showPassword ? (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                    <line x1="1" y1="1" x2="23" y2="23" />
                  </svg>
                ) : (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                )}
              </button>
            </div>
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%',
              padding: '16px',
              background: loading
                ? 'rgba(212,175,55,0.2)'
                : 'linear-gradient(135deg, #d4af37 0%, #996515 50%, #d4af37 100%)',
              backgroundSize: loading ? '100%' : '200% 100%',
              border: '1px solid rgba(255,255,255,0.15)',
              borderRadius: 10,
              color: '#000',
              fontSize: 12,
              fontWeight: 900,
              letterSpacing: '2px',
              cursor: loading ? 'wait' : 'pointer',
              boxShadow: loading
                ? 'none'
                : '0 8px 32px rgba(212,175,55,0.3), inset 0 1px 1px rgba(255,255,255,0.3)',
              transition: 'all 0.25s ease',
              textTransform: 'uppercase',
              fontFamily: C.mono,
              marginTop: 4,
            }}
            onMouseEnter={(e) => {
              if (!loading) {
                (e.currentTarget as HTMLButtonElement).style.backgroundPosition = '100% 0';
                (e.currentTarget as HTMLButtonElement).style.boxShadow = '0 10px 40px rgba(212,175,55,0.45), inset 0 1px 2px rgba(255,255,255,0.4)';
              }
            }}
            onMouseLeave={(e) => {
              if (!loading) {
                (e.currentTarget as HTMLButtonElement).style.backgroundPosition = '0 0';
                (e.currentTarget as HTMLButtonElement).style.boxShadow = '0 8px 32px rgba(212,175,55,0.3), inset 0 1px 1px rgba(255,255,255,0.3)';
              }
            }}
          >
            {loading ? 'AUTHENTICATING...' : 'ACCESS TERMINAL'}
          </button>
        </form>

        {/* Footer */}
        <div style={{
          marginTop: 28,
          textAlign: 'center',
          paddingTop: 18,
          borderTop: '1px solid rgba(255,255,255,0.05)',
        }}>
          <p style={{
            color: C.faint,
            fontSize: 8,
            margin: '0 0 6px 0',
            fontFamily: C.mono,
            letterSpacing: '0.5px',
          }}>
            CLEARANCE LEVEL: OBSIDIAN-30
          </p>
          <a
            href="https://github.com/qtu11/Autonomous-Trading-Engine"
            target="_blank"
            rel="noreferrer"
            style={{
              color: C.gold,
              fontSize: 10,
              textDecoration: 'none',
              fontWeight: 700,
              fontFamily: C.mono,
            }}
          >
            github.com/qtu11
          </a>
        </div>
      </div>
    </div>
  );
}
