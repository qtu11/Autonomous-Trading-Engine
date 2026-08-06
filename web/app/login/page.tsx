'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';

const API_ORIGIN = process.env.NEXT_PUBLIC_ATE_API_ORIGIN || process.env.NEXT_PUBLIC_QUANTAI_API_ORIGIN || '';

export default function LoginPage() {
  const router = useRouter();
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [focusedField, setFocusedField] = useState<string | null>(null);

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
      const res = await fetch(`${API_ORIGIN}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ login: login.trim(), password: password.trim() }),
      });

      const data = await res.json();

      if (res.ok && data.status === 'SUCCESS') {
        setSuccessMsg('Đăng nhập thành công! Đang chuyển hướng tới Trading Desk...');
        localStorage.setItem('quantai_auth_token', data.token || 'operator_authenticated');
        localStorage.setItem('quantai_user_info', JSON.stringify(data.user || {}));
        localStorage.setItem('firebase:authUser:qtusdev', JSON.stringify({ uid: 'qtusdev_admin', email: login.trim(), token: data.token }));
        document.cookie = `quantai_auth=${data.token}; path=/; max-age=315360000; SameSite=Lax`;

        setTimeout(() => {
          router.push('/');
        }, 800);
      } else {
        const msg = data.detail?.message || data.detail?.code || 'Sai thông tin đăng nhập quản trị!';
        setErrorMsg(msg);
      }
    } catch (err) {
      setErrorMsg('Không thể kết nối Backend API. Vui lòng kiểm tra dịch vụ backend (port 8005)!');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: '#04060a',
      backgroundImage: `
        radial-gradient(circle at 50% -10%, rgba(212, 175, 55, 0.12) 0%, transparent 60%),
        radial-gradient(circle at 10% 30%, rgba(59, 130, 246, 0.04) 0%, transparent 40%),
        radial-gradient(circle at 90% 80%, rgba(212, 175, 55, 0.05) 0%, transparent 40%),
        linear-gradient(to bottom, #030508 0%, #06090f 100%)
      `,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
      padding: '24px',
      position: 'relative',
      overflow: 'hidden',
    }}>
      {/* Dynamic Background Cyber Grid Lines */}
      <div style={{
        position: 'absolute',
        inset: 0,
        backgroundImage: `
          linear-gradient(to right, rgba(212, 175, 55, 0.015) 1px, transparent 1px),
          linear-gradient(to bottom, rgba(212, 175, 55, 0.015) 1px, transparent 1px)
        `,
        backgroundSize: '50px 50px',
        pointerEvents: 'none',
      }} />

      {/* Modern Glassmorphic Container Card */}
      <div style={{
        width: '100%',
        maxWidth: '460px',
        background: 'rgba(8, 12, 22, 0.65)',
        backdropFilter: 'blur(30px)',
        WebkitBackdropFilter: 'blur(30px)',
        border: '1px solid rgba(212, 175, 55, 0.15)',
        borderRadius: '24px',
        boxShadow: '0 25px 80px rgba(0, 0, 0, 0.8), 0 0 50px rgba(212, 175, 55, 0.05), inset 0 1px 1px rgba(255, 255, 255, 0.05)',
        padding: '44px 40px',
        position: 'relative',
        zIndex: 10,
        display: 'flex',
        flexDirection: 'column',
      }}>
        {/* Top Glow Accent Bar */}
        <div style={{
          position: 'absolute',
          top: 0,
          left: '10%',
          right: '10%',
          height: '2px',
          background: 'linear-gradient(90deg, transparent, #d4af37, transparent)',
          opacity: 0.8,
        }} />

        {/* Brand Header */}
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '64px',
            height: '64px',
            borderRadius: '16px',
            background: 'linear-gradient(135deg, rgba(212, 175, 55, 0.15) 0%, rgba(212, 175, 55, 0.02) 100%)',
            border: '1px solid rgba(212, 175, 55, 0.3)',
            marginBottom: '20px',
            boxShadow: '0 8px 24px rgba(0, 0, 0, 0.5), 0 0 20px rgba(212, 175, 55, 0.15)',
            position: 'relative',
          }}>
            <span style={{ fontSize: '28px', filter: 'drop-shadow(0 0 4px rgba(212, 175, 55, 0.5))' }}>⚡</span>
          </div>

          <h1 style={{
            color: '#ffffff',
            fontSize: '17px',
            fontWeight: 800,
            letterSpacing: '3px',
            margin: '0 0 8px 0',
            textTransform: 'uppercase',
            fontFamily: "'JetBrains Mono', monospace",
          }}>
            AUTONOMOUS <span style={{ color: '#d4af37' }}>TRADING</span> ENGINE
          </h1>
          <p style={{
            color: '#64748b',
            fontSize: '10px',
            margin: 0,
            letterSpacing: '1.2px',
            fontWeight: 700,
            textTransform: 'uppercase',
          }}>
            Institutional Desk &mdash; By QTusdev
          </p>
        </div>

        {/* Live System Specs Grid for High-Tech Aesthetic */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '8px',
          background: 'rgba(5, 7, 12, 0.6)',
          border: '1px solid rgba(255, 255, 255, 0.03)',
          borderRadius: '12px',
          padding: '10px 14px',
          marginBottom: '28px',
          fontSize: '9px',
          fontFamily: "'JetBrains Mono', monospace",
          color: '#475569',
        }}>
          <div>ATE CORE: <span style={{ color: '#10b981', fontWeight: 'bold' }}>ONLINE</span></div>
          <div>GATEWAY: <span style={{ color: '#3b82f6', fontWeight: 'bold' }}>MULTI_AI</span></div>
          <div>RISKGATE: <span style={{ color: '#d4af37', fontWeight: 'bold' }}>FAIL_SAFE</span></div>
          <div>MT5 BRIDGE: <span style={{ color: '#f59e0b', fontWeight: 'bold' }}>ACTIVE</span></div>
        </div>

        {/* Alert Notifications */}
        {errorMsg && (
          <div style={{
            background: 'rgba(239, 68, 68, 0.08)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            borderRadius: '12px',
            padding: '12px 16px',
            color: '#f87171',
            fontSize: '12px',
            fontWeight: 500,
            marginBottom: '20px',
            display: 'flex',
            alignItems: 'flex-start',
            gap: '10px',
            lineHeight: '1.4',
          }}>
            <span style={{ fontSize: '14px' }}>⚠️</span>
            <span>{errorMsg}</span>
          </div>
        )}

        {successMsg && (
          <div style={{
            background: 'rgba(16, 185, 129, 0.08)',
            border: '1px solid rgba(16, 185, 129, 0.3)',
            borderRadius: '12px',
            padding: '12px 16px',
            color: '#34d399',
            fontSize: '12px',
            fontWeight: 500,
            marginBottom: '20px',
            display: 'flex',
            alignItems: 'flex-start',
            gap: '10px',
            lineHeight: '1.4',
          }}>
            <span style={{ fontSize: '14px' }}>✅</span>
            <span>{successMsg}</span>
          </div>
        )}

        {/* Form Container */}
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Input Group: Login */}
          <div>
            <label style={{
              display: 'block',
              color: '#94a3b8',
              fontSize: '10px',
              fontWeight: 700,
              letterSpacing: '1px',
              marginBottom: '8px',
              textTransform: 'uppercase',
              fontFamily: "'JetBrains Mono', monospace",
            }}>
              Security Operator Email
            </label>
            <div style={{ position: 'relative' }}>
              <input
                type="text"
                value={login}
                onChange={(e) => setLogin(e.target.value)}
                onFocus={() => setFocusedField('login')}
                onBlur={() => setFocusedField(null)}
                placeholder="operator@trading-engine.ai"
                required
                style={{
                  width: '100%',
                  padding: '14px 16px',
                  background: 'rgba(5, 8, 14, 0.75)',
                  border: '1px solid',
                  borderColor: focusedField === 'login' ? '#d4af37' : 'rgba(255, 255, 255, 0.08)',
                  borderRadius: '12px',
                  color: '#ffffff',
                  fontSize: '14px',
                  outline: 'none',
                  transition: 'all 0.25s ease',
                  boxSizing: 'border-box',
                  boxShadow: focusedField === 'login' ? '0 0 15px rgba(212, 175, 55, 0.15)' : 'none',
                }}
              />
            </div>
          </div>

          {/* Input Group: Password */}
          <div>
            <label style={{
              display: 'block',
              color: '#94a3b8',
              fontSize: '10px',
              fontWeight: 700,
              letterSpacing: '1px',
              marginBottom: '8px',
              textTransform: 'uppercase',
              fontFamily: "'JetBrains Mono', monospace",
            }}>
              Operator Password
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
                  background: 'rgba(5, 8, 14, 0.75)',
                  border: '1px solid',
                  borderColor: focusedField === 'password' ? '#d4af37' : 'rgba(255, 255, 255, 0.08)',
                  borderRadius: '12px',
                  color: '#ffffff',
                  fontSize: '14px',
                  outline: 'none',
                  transition: 'all 0.25s ease',
                  boxSizing: 'border-box',
                  boxShadow: focusedField === 'password' ? '0 0 15px rgba(212, 175, 55, 0.15)' : 'none',
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
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  outline: 'none',
                }}
              >
                {showPassword ? '🙈' : '👁️'}
              </button>
            </div>
          </div>

          {/* Action Trigger Button */}
          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%',
              padding: '15px',
              background: loading
                ? 'rgba(212, 175, 55, 0.3)'
                : 'linear-gradient(135deg, #d4af37 0%, #b8860b 100%)',
              border: 'none',
              borderRadius: '12px',
              color: '#000000',
              fontSize: '13px',
              fontWeight: 800,
              letterSpacing: '1.5px',
              cursor: loading ? 'wait' : 'pointer',
              boxShadow: loading ? 'none' : '0 6px 24px rgba(212, 175, 55, 0.25)',
              transition: 'all 0.25s ease',
              textTransform: 'uppercase',
              fontFamily: "'JetBrains Mono', monospace",
              marginTop: '8px',
            }}
          >
            {loading ? 'SECURING NETWORK...' : 'INITIALIZE TRADING SESSION'}
          </button>
        </form>

        {/* Premium footer specs */}
        <div style={{
          marginTop: '36px',
          textAlign: 'center',
          borderTop: '1px solid rgba(255, 255, 255, 0.05)',
          paddingTop: '20px',
        }}>
          <p style={{
            color: '#475569',
            fontSize: '9px',
            margin: '0 0 6px 0',
            fontFamily: "'JetBrains Mono', monospace",
            letterSpacing: '0.5px',
          }}>
            SECURITY LEVEL: PROTOCOL_30_MARG_ARMED
          </p>
          <a
            href="https://github.com/qtu11/Autonomous-Trading-Engine"
            target="_blank"
            rel="noreferrer"
            style={{
              color: '#d4af37',
              fontSize: '11px',
              textDecoration: 'none',
              fontWeight: 600,
              fontFamily: "'JetBrains Mono', monospace",
              transition: 'opacity 0.2s',
            }}
            onMouseOver={(e) => (e.currentTarget.style.opacity = '0.8')}
            onMouseOut={(e) => (e.currentTarget.style.opacity = '1')}
          >
            github.com/qtu11/ATE
          </a>
        </div>
      </div>
    </div>
  );
}

