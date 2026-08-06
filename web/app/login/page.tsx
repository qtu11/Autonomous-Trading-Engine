'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';

const API_ORIGIN = process.env.NEXT_PUBLIC_ATE_API_ORIGIN || process.env.NEXT_PUBLIC_QUANTAI_API_ORIGIN || '';

// Mock Live Market Ticker Data for Institutional Stock/Gold Desk Visuals
const TICKER_ITEMS = [
  { symbol: 'XAU/USD', price: '2,845.50', change: '+1.24%', isUp: true },
  { symbol: 'SPX 500', price: '5,980.20', change: '+0.45%', isUp: true },
  { symbol: 'NASDAQ 100', price: '21,450.80', change: '+0.82%', isUp: true },
  { symbol: 'BTC/USD', price: '98,400.00', change: '-0.35%', isUp: false },
  { symbol: 'EUR/USD', price: '1.0845', change: '+0.12%', isUp: true },
  { symbol: 'US 10Y YIELD', price: '4.28%', change: '-0.04%', isUp: false },
  { symbol: 'DXY INDEX', price: '104.15', change: '-0.18%', isUp: false },
  { symbol: 'BRENT CRUDE', price: '76.40', change: '+0.95%', isUp: true },
];

export default function LoginPage() {
  const router = useRouter();
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [focusedField, setFocusedField] = useState<string | null>(null);

  // 3D Tilt Effect State
  const cardRef = useRef<HTMLDivElement>(null);
  const [transformStyle, setTransformStyle] = useState('perspective(1000px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)');
  const [glareStyle, setGlareStyle] = useState({ opacity: 0, x: 50, y: 50 });

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!cardRef.current) return;
    const rect = cardRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const centerX = rect.width / 2;
    const centerY = rect.height / 2;
    
    // Rotate max +- 8 degrees
    const rotateX = ((y - centerY) / centerY) * -8;
    const rotateY = ((x - centerX) / centerX) * 8;
    
    setTransformStyle(`perspective(1000px) rotateX(${rotateX.toFixed(2)}deg) rotateY(${rotateY.toFixed(2)}deg) scale3d(1.02, 1.02, 1.02)`);
    setGlareStyle({
      opacity: 0.15,
      x: (x / rect.width) * 100,
      y: (y / rect.height) * 100,
    });
  };

  const handleMouseLeave = () => {
    setTransformStyle('perspective(1000px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)');
    setGlareStyle({ opacity: 0, x: 50, y: 50 });
  };

  useEffect(() => {
    // If already authenticated, redirect to desk
    const savedToken = localStorage.getItem('quantai_auth_token');
    if (savedToken) {
      router.push('/');
    }
  }, [router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg('');
    setSuccessMsg('');

    if (!login.trim() || !password.trim()) {
      setErrorMsg('Vui lòng nhập Tên đăng nhập và Mật khẩu!');
      return;
    }

    setLoading(true);

    try {
      const endpoint = API_ORIGIN ? `${API_ORIGIN}/api/auth/login` : '/api/auth/login';
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ login: login.trim(), password: password.trim() }),
      });

      const data = await res.json();

      if (res.ok && data.status === 'SUCCESS') {
        setSuccessMsg('Xác thực quyền thành công! Đang vào sàn giao dịch...');
        localStorage.setItem('quantai_auth_token', data.token || 'operator_authenticated');
        localStorage.setItem('quantai_user_info', JSON.stringify(data.user || {}));
        localStorage.setItem('firebase:authUser:qtusdev', JSON.stringify({ uid: 'qtusdev_admin', email: login.trim(), token: data.token }));
        document.cookie = `quantai_auth=${data.token}; path=/; max-age=315360000; SameSite=Lax`;

        setTimeout(() => {
          router.push('/');
        }, 800);
      } else {
        const msg = data.detail?.message || data.detail?.code || 'Không thể xác thực thông tin tài khoản Quản trị!';
        setErrorMsg(msg);
      }
    } catch (err) {
      setErrorMsg('Không thể kết nối API Backend. Vui lòng kiểm tra dịch vụ backend (port 8005)!');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: '#030508',
      backgroundImage: `
        radial-gradient(circle at 50% 0%, rgba(212, 175, 55, 0.14) 0%, transparent 65%),
        radial-gradient(circle at 15% 40%, rgba(16, 185, 129, 0.05) 0%, transparent 45%),
        radial-gradient(circle at 85% 75%, rgba(59, 130, 246, 0.06) 0%, transparent 50%),
        linear-gradient(to bottom, #020305 0%, #06090e 100%)
      `,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
      padding: '0 20px',
      position: 'relative',
      overflow: 'hidden',
    }}>
      {/* ── TOP FINANCIAL LIVE MARKET TICKER MARQUEE ── */}
      <div style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        height: '36px',
        background: 'rgba(5, 8, 14, 0.85)',
        borderBottom: '1px solid rgba(212, 175, 55, 0.15)',
        backdropFilter: 'blur(12px)',
        zIndex: 100,
        display: 'flex',
        alignItems: 'center',
        overflow: 'hidden',
        boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
      }}>
        <div style={{
          background: 'linear-gradient(135deg, #d4af37, #996515)',
          color: '#000000',
          padding: '0 12px',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          fontWeight: 900,
          fontSize: '10px',
          letterSpacing: '1px',
          fontFamily: "'JetBrains Mono', monospace",
          zIndex: 10,
          boxShadow: '4px 0 12px rgba(0,0,0,0.4)',
        }}>
          MARKETS LIVE
        </div>

        <div className="animate-marquee" style={{ gap: '32px', paddingLeft: '20px' }}>
          {[...TICKER_ITEMS, ...TICKER_ITEMS].map((item, idx) => (
            <div key={idx} style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: '11px',
              fontFamily: "'JetBrains Mono', monospace",
            }}>
              <span style={{ color: '#94a3b8', fontWeight: 600 }}>{item.symbol}</span>
              <span style={{ color: '#ffffff', fontWeight: 700 }}>{item.price}</span>
              <span style={{
                color: item.isUp ? '#10b981' : '#ef4444',
                fontWeight: 700,
                fontSize: '10px',
                background: item.isUp ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                padding: '2px 6px',
                borderRadius: '4px',
              }}>
                {item.change}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* ── BACKGROUND CANDLESTICK SVG GRAPHICS ── */}
      <div style={{
        position: 'absolute',
        inset: 0,
        opacity: 0.12,
        pointerEvents: 'none',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '0 5%',
      }}>
        {/* Left Side Financial Candlestick Visualizer */}
        <svg width="320" height="400" viewBox="0 0 320 400" fill="none">
          <line x1="40" y1="50" x2="40" y2="350" stroke="#10b981" strokeWidth="1" strokeDasharray="3 3" />
          <line x1="120" y1="50" x2="120" y2="350" stroke="#ef4444" strokeWidth="1" strokeDasharray="3 3" />
          <line x1="200" y1="50" x2="200" y2="350" stroke="#10b981" strokeWidth="1" strokeDasharray="3 3" />
          <line x1="280" y1="50" x2="280" y2="350" stroke="#d4af37" strokeWidth="1" strokeDasharray="3 3" />

          {/* Green Bullish Candlestick */}
          <line x1="60" y1="80" x2="60" y2="280" stroke="#10b981" strokeWidth="2" />
          <rect x="48" y="120" width="24" height="110" fill="#10b981" rx="2" />

          {/* Red Bearish Candlestick */}
          <line x1="140" y1="60" x2="140" y2="320" stroke="#ef4444" strokeWidth="2" />
          <rect x="128" y="100" width="24" height="150" fill="#ef4444" rx="2" />

          {/* Gold Breakout Candlestick */}
          <line x1="220" y1="40" x2="220" y2="360" stroke="#d4af37" strokeWidth="2" />
          <rect x="208" y="70" width="24" height="210" fill="url(#goldGrad)" rx="2" />
          
          <defs>
            <linearGradient id="goldGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#d4af37" />
              <stop offset="100%" stopColor="#996515" />
            </linearGradient>
          </defs>
        </svg>

        {/* Right Side Order Depth Graph Visualizer */}
        <svg width="320" height="400" viewBox="0 0 320 400" fill="none">
          <path d="M0 350 Q 80 300, 140 220 T 320 50" fill="none" stroke="#10b981" strokeWidth="3" />
          <path d="M0 350 Q 80 300, 140 220 T 320 50 L 320 400 L 0 400 Z" fill="url(#greenAreaGrad)" opacity="0.15" />

          <path d="M0 50 Q 120 180, 180 260 T 320 380" fill="none" stroke="#ef4444" strokeWidth="2" strokeDasharray="4 4" />
          
          <defs>
            <linearGradient id="greenAreaGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#10b981" />
              <stop offset="100%" stopColor="transparent" />
            </linearGradient>
          </defs>
        </svg>
      </div>

      {/* ── 3D INTERACTIVE TILT CONTAINER CARD ── */}
      <div
        ref={cardRef}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        className="glow-border-3d"
        style={{
          width: '100%',
          maxWidth: '480px',
          background: 'rgba(8, 12, 22, 0.75)',
          backdropFilter: 'blur(35px)',
          WebkitBackdropFilter: 'blur(35px)',
          borderRadius: '24px',
          boxShadow: '0 30px 100px rgba(0, 0, 0, 0.9), 0 0 60px rgba(212, 175, 55, 0.12), inset 0 1px 1px rgba(255, 255, 255, 0.1)',
          padding: '44px 40px',
          position: 'relative',
          zIndex: 10,
          transform: transformStyle,
          transition: 'transform 0.15s ease-out, box-shadow 0.3s ease',
          transformStyle: 'preserve-3d',
          marginTop: '36px',
        }}
      >
        {/* Dynamic Light Reflection Glare */}
        <div style={{
          position: 'absolute',
          inset: 0,
          borderRadius: '24px',
          background: `radial-gradient(circle at ${glareStyle.x}% ${glareStyle.y}%, rgba(255, 255, 255, ${glareStyle.opacity}), transparent 60%)`,
          pointerEvents: 'none',
          transition: 'opacity 0.2s ease',
        }} />

        {/* Top Gold Metallic Badge */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '28px',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
          paddingBottom: '16px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              backgroundColor: '#10b981',
              boxShadow: '0 0 10px #10b981',
            }} />
            <span style={{
              fontSize: '10px',
              fontFamily: "'JetBrains Mono', monospace",
              color: '#d4af37',
              fontWeight: 800,
              letterSpacing: '1px',
            }}>
              ATE FINANCIAL DESK
            </span>
          </div>

          <div style={{
            fontSize: '9px',
            fontFamily: "'JetBrains Mono', monospace",
            color: '#64748b',
            background: 'rgba(255, 255, 255, 0.04)',
            padding: '3px 8px',
            borderRadius: '6px',
            border: '1px solid rgba(255, 255, 255, 0.06)',
          }}>
            VERCEL SECURE
          </div>
        </div>

        {/* Brand Header */}
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '68px',
            height: '68px',
            borderRadius: '20px',
            background: 'linear-gradient(145deg, rgba(212, 175, 55, 0.2) 0%, rgba(10, 15, 28, 0.8) 100%)',
            border: '1px solid rgba(212, 175, 55, 0.4)',
            marginBottom: '16px',
            boxShadow: '0 12px 30px rgba(0, 0, 0, 0.6), 0 0 25px rgba(212, 175, 55, 0.25)',
            transform: 'translateZ(30px)',
          }}>
            <span style={{ fontSize: '32px', filter: 'drop-shadow(0 0 6px rgba(212, 175, 55, 0.6))' }}>🏛️</span>
          </div>

          <h1 style={{
            color: '#ffffff',
            fontSize: '18px',
            fontWeight: 900,
            letterSpacing: '3px',
            margin: '0 0 6px 0',
            textTransform: 'uppercase',
            fontFamily: "'JetBrains Mono', monospace",
            transform: 'translateZ(25px)',
          }}>
            AUTONOMOUS <span style={{ color: '#d4af37' }}>TRADING</span> ENGINE
          </h1>
          <p style={{
            color: '#64748b',
            fontSize: '10px',
            margin: 0,
            letterSpacing: '1.5px',
            fontWeight: 700,
            textTransform: 'uppercase',
            transform: 'translateZ(20px)',
          }}>
            Institutional Stock & Gold Terminal &mdash; By QTusdev
          </p>
        </div>

        {/* Financial Metrics Live Telemetry Grid */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr 1fr',
          gap: '8px',
          background: 'rgba(5, 7, 12, 0.7)',
          border: '1px solid rgba(212, 175, 55, 0.1)',
          borderRadius: '14px',
          padding: '12px',
          marginBottom: '28px',
          fontSize: '9px',
          fontFamily: "'JetBrains Mono', monospace",
          transform: 'translateZ(15px)',
        }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ color: '#64748b', fontSize: '8px', marginBottom: '2px' }}>GATEWAY</div>
            <div style={{ color: '#3b82f6', fontWeight: 'bold' }}>MULTI_AI 2026</div>
          </div>
          <div style={{ textAlign: 'center', borderLeft: '1px solid rgba(255,255,255,0.06)', borderRight: '1px solid rgba(255,255,255,0.06)' }}>
            <div style={{ color: '#64748b', fontSize: '8px', marginBottom: '2px' }}>RISKGATE</div>
            <div style={{ color: '#d4af37', fontWeight: 'bold' }}>ARMED 1%</div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ color: '#64748b', fontSize: '8px', marginBottom: '2px' }}>MT5 ENGINE</div>
            <div style={{ color: '#10b981', fontWeight: 'bold' }}>ONLINE</div>
          </div>
        </div>

        {/* Status Alerts */}
        {errorMsg && (
          <div style={{
            background: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.4)',
            borderRadius: '12px',
            padding: '12px 16px',
            color: '#f87171',
            fontSize: '12px',
            fontWeight: 600,
            marginBottom: '20px',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            transform: 'translateZ(20px)',
          }}>
            <span>⚠️</span>
            <span>{errorMsg}</span>
          </div>
        )}

        {successMsg && (
          <div style={{
            background: 'rgba(16, 185, 129, 0.1)',
            border: '1px solid rgba(16, 185, 129, 0.4)',
            borderRadius: '12px',
            padding: '12px 16px',
            color: '#34d399',
            fontSize: '12px',
            fontWeight: 600,
            marginBottom: '20px',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            transform: 'translateZ(20px)',
          }}>
            <span>✅</span>
            <span>{successMsg}</span>
          </div>
        )}

        {/* Input Form */}
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '22px', transform: 'translateZ(20px)' }}>
          {/* Operator Login */}
          <div>
            <label style={{
              display: 'block',
              color: '#94a3b8',
              fontSize: '10px',
              fontWeight: 800,
              letterSpacing: '1px',
              marginBottom: '8px',
              textTransform: 'uppercase',
              fontFamily: "'JetBrains Mono', monospace",
            }}>
              Operator Email / Identity
            </label>
            <div style={{ position: 'relative' }}>
              <input
                type="text"
                value={login}
                onChange={(e) => setLogin(e.target.value)}
                onFocus={() => setFocusedField('login')}
                onBlur={() => setFocusedField(null)}
                placeholder="qtusdev@quanttrading.ai"
                required
                style={{
                  width: '100%',
                  padding: '14px 16px',
                  background: 'rgba(5, 8, 14, 0.85)',
                  border: '1px solid',
                  borderColor: focusedField === 'login' ? '#d4af37' : 'rgba(255, 255, 255, 0.1)',
                  borderRadius: '12px',
                  color: '#ffffff',
                  fontSize: '14px',
                  outline: 'none',
                  transition: 'all 0.25s ease',
                  boxSizing: 'border-box',
                  boxShadow: focusedField === 'login' ? '0 0 20px rgba(212, 175, 55, 0.25)' : 'none',
                  fontFamily: "'JetBrains Mono', monospace",
                }}
              />
            </div>
          </div>

          {/* Operator Password */}
          <div>
            <label style={{
              display: 'block',
              color: '#94a3b8',
              fontSize: '10px',
              fontWeight: 800,
              letterSpacing: '1px',
              marginBottom: '8px',
              textTransform: 'uppercase',
              fontFamily: "'JetBrains Mono', monospace",
            }}>
              Operator Security Key
            </label>
            <div style={{ position: 'relative' }}>
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onFocus={() => setFocusedField('password')}
                onBlur={() => setFocusedField(null)}
                placeholder="••••••••••••"
                required
                style={{
                  width: '100%',
                  padding: '14px 46px 14px 16px',
                  background: 'rgba(5, 8, 14, 0.85)',
                  border: '1px solid',
                  borderColor: focusedField === 'password' ? '#d4af37' : 'rgba(255, 255, 255, 0.1)',
                  borderRadius: '12px',
                  color: '#ffffff',
                  fontSize: '14px',
                  outline: 'none',
                  transition: 'all 0.25s ease',
                  boxSizing: 'border-box',
                  boxShadow: focusedField === 'password' ? '0 0 20px rgba(212, 175, 55, 0.25)' : 'none',
                  fontFamily: "'JetBrains Mono', monospace",
                }}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                style={{
                  position: 'absolute',
                  right: '16px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none',
                  border: 'none',
                  color: '#64748b',
                  cursor: 'pointer',
                  fontSize: '15px',
                  padding: 0,
                  outline: 'none',
                }}
              >
                {showPassword ? '🙈' : '👁️'}
              </button>
            </div>
          </div>

          {/* Metallic 3D Action Button */}
          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%',
              padding: '16px',
              background: loading
                ? 'rgba(212, 175, 55, 0.3)'
                : 'linear-gradient(135deg, #f39c12 0%, #d4af37 50%, #996515 100%)',
              border: '1px solid rgba(255, 255, 255, 0.2)',
              borderRadius: '12px',
              color: '#000000',
              fontSize: '13px',
              fontWeight: 900,
              letterSpacing: '2px',
              cursor: loading ? 'wait' : 'pointer',
              boxShadow: loading ? 'none' : '0 8px 30px rgba(212, 175, 55, 0.35), inset 0 1px 1px rgba(255, 255, 255, 0.4)',
              transition: 'all 0.25s ease',
              textTransform: 'uppercase',
              fontFamily: "'JetBrains Mono', monospace",
              marginTop: '6px',
            }}
          >
            {loading ? 'AUTHENTICATING ENCRYPTED SESSION...' : 'ACCESS TRADING DESK'}
          </button>
        </form>

        {/* Footer info */}
        <div style={{
          marginTop: '32px',
          textAlign: 'center',
          borderTop: '1px solid rgba(255, 255, 255, 0.06)',
          paddingTop: '18px',
          transform: 'translateZ(15px)',
        }}>
          <p style={{
            color: '#475569',
            fontSize: '9px',
            margin: '0 0 6px 0',
            fontFamily: "'JetBrains Mono', monospace",
          }}>
            SECURITY CLEARANCE: LEVEL_30_OBSIDIAN
          </p>
          <a
            href="https://github.com/qtu11/Autonomous-Trading-Engine"
            target="_blank"
            rel="noreferrer"
            style={{
              color: '#d4af37',
              fontSize: '11px',
              textDecoration: 'none',
              fontWeight: 700,
              fontFamily: "'JetBrains Mono', monospace",
            }}
          >
            github.com/qtu11/Autonomous-Trading-Engine
          </a>
        </div>
      </div>
    </div>
  );
}


