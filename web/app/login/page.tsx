'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';

const API_ORIGIN = process.env.NEXT_PUBLIC_ATE_API_ORIGIN || process.env.NEXT_PUBLIC_QUANTAI_API_ORIGIN || 'http://127.0.0.1:8005';

export default function LoginPage() {
  const router = useRouter();
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

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
      backgroundColor: '#05070a',
      backgroundImage: `
        radial-gradient(circle at 50% 20%, rgba(212, 175, 55, 0.15) 0%, transparent 60%),
        radial-gradient(circle at 80% 80%, rgba(59, 130, 246, 0.08) 0%, transparent 50%),
        linear-gradient(to bottom, #05070a 0%, #080c14 100%)
      `,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace',
      padding: '20px',
      position: 'relative',
      overflow: 'hidden',
    }}>
      {/* Background Cyber Grid Lines */}
      <div style={{
        position: 'absolute',
        inset: 0,
        backgroundImage: `
          linear-gradient(to right, rgba(255, 255, 255, 0.02) 1px, transparent 1px),
          linear-gradient(to bottom, rgba(255, 255, 255, 0.02) 1px, transparent 1px)
        `,
        backgroundSize: '40px 40px',
        pointerEvents: 'none',
      }} />

      {/* Glassmorphism Card */}
      <div style={{
        width: '100%',
        maxWidth: '440px',
        background: 'rgba(12, 17, 26, 0.85)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        border: '1px solid rgba(212, 175, 55, 0.3)',
        borderRadius: '16px',
        boxShadow: '0 20px 60px rgba(0, 0, 0, 0.7), 0 0 40px rgba(212, 175, 55, 0.15)',
        padding: '36px 32px',
        position: 'relative',
        zIndex: 10,
      }}>
        {/* Header Branding */}
        <div style={{ textAlign: 'center', marginBottom: '28px' }}>
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '56px',
            height: '56px',
            borderRadius: '12px',
            background: 'linear-gradient(135deg, rgba(212, 175, 55, 0.25) 0%, rgba(212, 175, 55, 0.05) 100%)',
            border: '1px solid rgba(212, 175, 55, 0.5)',
            marginBottom: '14px',
            boxShadow: '0 0 20px rgba(212, 175, 55, 0.3)',
          }}>
            <span style={{ fontSize: '26px' }}>🤖</span>
          </div>

          <h1 style={{
            color: '#ffffff',
            fontSize: '22px',
            fontWeight: 800,
            letterSpacing: '1.5px',
            margin: '0 0 6px 0',
            textTransform: 'uppercase',
          }}>
            GOLDQUANT <span style={{ color: '#d4af37' }}>AI</span>
          </h1>
          <p style={{
            color: '#8b9bb4',
            fontSize: '11px',
            margin: 0,
            letterSpacing: '0.8px',
            fontWeight: 600,
          }}>
            BLOOMBERG TRADING DESK &mdash; BY QTUSDEV (NGUYỄN QUANG TÚ)
          </p>
        </div>

        {/* Status Alerts */}
        {errorMsg && (
          <div style={{
            background: 'rgba(239, 68, 68, 0.15)',
            border: '1px solid rgba(239, 68, 68, 0.5)',
            borderRadius: '8px',
            padding: '10px 14px',
            color: '#ef4444',
            fontSize: '12px',
            fontWeight: 600,
            marginBottom: '18px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}>
            <span>⚠️</span>
            <span>{errorMsg}</span>
          </div>
        )}

        {successMsg && (
          <div style={{
            background: 'rgba(16, 185, 129, 0.15)',
            border: '1px solid rgba(16, 185, 129, 0.5)',
            borderRadius: '8px',
            padding: '10px 14px',
            color: '#10b981',
            fontSize: '12px',
            fontWeight: 600,
            marginBottom: '18px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}>
            <span>✅</span>
            <span>{successMsg}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit}>
          {/* Admin Login Input */}
          <div style={{ marginBottom: '18px' }}>
            <label style={{
              display: 'block',
              color: '#d1d5db',
              fontSize: '11px',
              fontWeight: 700,
              letterSpacing: '0.5px',
              marginBottom: '6px',
              textTransform: 'uppercase',
            }}>
              ADMIN EMAIL / LOGIN
            </label>
            <div style={{ position: 'relative' }}>
              <input
                type="text"
                value={login}
                onChange={(e) => setLogin(e.target.value)}
                placeholder="Nhập email quản trị (từ file .env)..."
                required
                style={{
                  width: '100%',
                  padding: '12px 14px',
                  background: 'rgba(5, 8, 14, 0.85)',
                  border: '1px solid rgba(212, 175, 55, 0.3)',
                  borderRadius: '8px',
                  color: '#ffffff',
                  fontSize: '13px',
                  outline: 'none',
                  transition: 'all 0.2s ease',
                  boxSizing: 'border-box',
                }}
                onFocus={(e) => (e.target.style.borderColor = '#d4af37')}
                onBlur={(e) => (e.target.style.borderColor = 'rgba(212, 175, 55, 0.3)')}
              />
            </div>
          </div>

          {/* Admin Password Input */}
          <div style={{ marginBottom: '24px' }}>
            <label style={{
              display: 'block',
              color: '#d1d5db',
              fontSize: '11px',
              fontWeight: 700,
              letterSpacing: '0.5px',
              marginBottom: '6px',
              textTransform: 'uppercase',
            }}>
              ADMIN PASSWORD
            </label>
            <div style={{ position: 'relative' }}>
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Nhập mật khẩu quản trị (từ file .env)..."
                required
                style={{
                  width: '100%',
                  padding: '12px 40px 12px 14px',
                  background: 'rgba(5, 8, 14, 0.85)',
                  border: '1px solid rgba(212, 175, 55, 0.3)',
                  borderRadius: '8px',
                  color: '#ffffff',
                  fontSize: '13px',
                  outline: 'none',
                  transition: 'all 0.2s ease',
                  boxSizing: 'border-box',
                }}
                onFocus={(e) => (e.target.style.borderColor = '#d4af37')}
                onBlur={(e) => (e.target.style.borderColor = 'rgba(212, 175, 55, 0.3)')}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                style={{
                  position: 'absolute',
                  right: '12px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none',
                  border: 'none',
                  color: '#8b9bb4',
                  cursor: 'pointer',
                  fontSize: '13px',
                  padding: 0,
                }}
              >
                {showPassword ? '🙈' : '👁️'}
              </button>
            </div>
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%',
              padding: '13px',
              background: loading
                ? 'rgba(212, 175, 55, 0.4)'
                : 'linear-gradient(135deg, #d4af37 0%, #b8860b 100%)',
              border: 'none',
              borderRadius: '8px',
              color: '#000000',
              fontSize: '13px',
              fontWeight: 800,
              letterSpacing: '1px',
              cursor: loading ? 'wait' : 'pointer',
              boxShadow: loading ? 'none' : '0 4px 20px rgba(212, 175, 55, 0.35)',
              transition: 'all 0.2s ease',
              textTransform: 'uppercase',
            }}
          >
            {loading ? 'ĐANG XÁC THỰC AI...' : 'ĐĂNG NHẬP HỆ THỐNG TRADING'}
          </button>
        </form>

        {/* Footer info */}
        <div style={{
          marginTop: '24px',
          textAlign: 'center',
          borderTop: '1px solid rgba(255, 255, 255, 0.08)',
          paddingTop: '16px',
        }}>
          <p style={{ color: '#6b7280', fontSize: '10px', margin: '0 0 4px 0' }}>
            Hệ thống Quản trị AI & Chốt chặn Rủi ro Margin 30%
          </p>
          <a
            href="https://github.com/qtu11"
            target="_blank"
            rel="noreferrer"
            style={{ color: '#d4af37', fontSize: '11px', textDecoration: 'none', fontWeight: 600 }}
          >
            https://github.com/qtu11
          </a>
        </div>
      </div>
    </div>
  );
}
