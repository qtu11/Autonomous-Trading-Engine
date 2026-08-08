'use client';

import { useState, useEffect, useRef, useCallback, type CSSProperties } from 'react';
import {
  fetchControlCenterStatus,
  updateControlMode,
  updateControlKillSwitch,
  updateControlDemoArm,
  updateAiAutoLoop,
  loginMT5Account,
  updateControlRisk,
  updateTelegramConfig,
  fetchAIConfig,
  updateAIConfig,
  testAIConnection,
  createStreamSocket,
  type ControlCenterStatus,
} from '../../lib/api';

// ── Design tokens ─────────────────────────────────────────────────────────────
const C = {
  gold: '#D4B483',
  goldBright: '#F0D5A0',
  goldDim: 'rgba(212,180,131,0.15)',
  green: '#22d3a0',
  greenDim: 'rgba(34,211,160,0.12)',
  red: '#f43f5e',
  redDim: 'rgba(244,63,94,0.12)',
  blue: '#38bdf8',
  blueDim: 'rgba(56,189,248,0.12)',
  text: '#e2e8f0',
  dim: '#94a3b8',
  muted: '#64748b',
  faint: '#475569',
  bg: '#0a0d14',
  bgCard: 'rgba(255,255,255,0.03)',
  border: 'rgba(255,255,255,0.08)',
  borderGold: 'rgba(212,180,131,0.25)',
  mono: '"JetBrains Mono", monospace',
  sans: '"Inter", sans-serif',
};

// ── Shared styles ─────────────────────────────────────────────────────────────
const card: CSSProperties = {
  background: C.bgCard,
  borderWidth: '1px',
  borderStyle: 'solid',
  borderColor: C.border,
  borderRadius: 12,
  padding: '16px 18px',
  transition: 'border-color 0.2s ease, box-shadow 0.2s ease',
};

const cardHover: CSSProperties = {
  borderColor: C.borderGold,
  boxShadow: '0 4px 24px rgba(0,0,0,0.35), 0 0 0 1px rgba(212,180,131,0.08)',
};

const label: CSSProperties = {
  fontSize: 9,
  color: C.muted,
  fontFamily: C.mono,
  letterSpacing: '0.12em',
  textTransform: 'uppercase',
  display: 'block',
  marginBottom: 6,
  fontWeight: 600,
};

const input: CSSProperties = {
  width: '100%',
  padding: '9px 12px',
  background: 'rgba(0,0,0,0.5)',
  border: `1px solid ${C.border}`,
  borderRadius: 8,
  color: C.text,
  fontSize: 12,
  fontFamily: C.mono,
  boxSizing: 'border-box',
  outline: 'none',
  transition: 'border-color 0.2s, box-shadow 0.2s',
};

const btnBase: CSSProperties = {
  padding: '10px 16px',
  fontSize: 11,
  fontFamily: C.mono,
  fontWeight: 700,
  borderRadius: 8,
  cursor: 'pointer',
  border: 'none',
  transition: 'all 0.2s ease',
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 6,
};

// ── Micro components ──────────────────────────────────────────────────────────
function SectionHeader({ num, title, sub }: { num: string; title: string; sub?: string }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span
          style={{
            width: 24,
            height: 24,
            borderRadius: 6,
            background: `linear-gradient(135deg, ${C.goldDim}, rgba(212,180,131,0.05))`,
            border: `1px solid ${C.borderGold}`,
            color: C.gold,
            fontSize: 11,
            fontWeight: 800,
            fontFamily: C.mono,
            display: 'grid',
            placeItems: 'center',
            flexShrink: 0,
          }}
        >
          {num}
        </span>
        <span style={{ fontSize: 12, fontWeight: 700, color: C.gold, fontFamily: C.mono, letterSpacing: '0.08em' }}>{title}</span>
      </div>
      {sub && <div style={{ fontSize: 10, color: C.muted, marginTop: 5, marginLeft: 34, fontFamily: C.sans, lineHeight: 1.4 }}>{sub}</div>}
    </div>
  );
}

function StatusPill({ ok, labelOk, labelBad }: { ok: boolean; labelOk: string; labelBad: string }) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '4px 10px',
        borderRadius: 20,
        fontSize: 9,
        fontWeight: 700,
        fontFamily: C.mono,
        letterSpacing: '0.05em',
        background: ok ? C.greenDim : C.redDim,
        border: `1px solid ${ok ? 'rgba(34,211,160,0.35)' : 'rgba(244,63,94,0.35)'}`,
        color: ok ? C.green : C.red,
      }}
    >
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: '50%',
          background: ok ? C.green : C.red,
          boxShadow: ok ? `0 0 8px ${C.green}` : `0 0 8px ${C.red}`,
        }}
      />
      {ok ? labelOk : labelBad}
    </span>
  );
}

function Toast({ msg, err }: { msg: string; err: boolean }) {
  return (
    <div
      role="status"
      style={{
        marginTop: 10,
        padding: '10px 14px',
        borderRadius: 8,
        fontSize: 11,
        fontFamily: C.mono,
        background: err ? C.redDim : C.greenDim,
        border: `1px solid ${err ? 'rgba(244,63,94,0.4)' : 'rgba(34,211,160,0.4)'}`,
        color: err ? C.red : C.green,
        animation: 'ccFadeIn 0.3s ease',
        display: 'flex',
        alignItems: 'center',
        gap: 8,
      }}
    >
      <span style={{ fontSize: 14 }}>{err ? '✕' : '✓'}</span>
      {msg}
    </div>
  );
}

function Spinner() {
  return (
    <span
      style={{
        display: 'inline-block',
        width: 12,
        height: 12,
        border: '2px solid rgba(255,255,255,0.2)',
        borderTopColor: 'currentColor',
        borderRadius: '50%',
        animation: 'ccSpin 0.8s linear infinite',
      }}
    />
  );
}

function KV({ k, v, color }: { k: string; v: string; color?: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 0', borderBottom: `1px solid ${C.border}` }}>
      <span style={{ fontSize: 11, color: C.muted, fontFamily: C.sans }}>{k}</span>
      <span style={{ fontSize: 11, color: color || C.text, fontFamily: C.mono, fontWeight: 600 }}>{v}</span>
    </div>
  );
}

function ToggleSwitch({ active, onChange, disabled, activeColor = C.green }: { active: boolean; onChange: () => void; disabled?: boolean; activeColor?: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={active}
      disabled={disabled}
      onClick={onChange}
      style={{
        width: 44,
        height: 24,
        borderRadius: 12,
        background: active ? activeColor : 'rgba(255,255,255,0.1)',
        border: `1px solid ${active ? activeColor : C.border}`,
        cursor: disabled ? 'not-allowed' : 'pointer',
        position: 'relative',
        transition: 'all 0.25s ease',
        opacity: disabled ? 0.5 : 1,
        flexShrink: 0,
      }}
    >
      <span
        style={{
          position: 'absolute',
          top: 2,
          left: active ? 22 : 2,
          width: 18,
          height: 18,
          borderRadius: '50%',
          background: '#fff',
          transition: 'left 0.25s ease',
          boxShadow: '0 2px 6px rgba(0,0,0,0.3)',
        }}
      />
    </button>
  );
}

// ── Main Control Center ───────────────────────────────────────────────────────
export default function ControlCenter({
  open,
  onClose,
  triggerRef,
}: {
  open: boolean;
  onClose: () => void;
  triggerRef: React.RefObject<HTMLButtonElement | null>;
}) {
  const [cc, setCc] = useState<ControlCenterStatus | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [toast, setToast] = useState<{ msg: string; err: boolean } | null>(null);
  const [hoveredCard, setHoveredCard] = useState<string | null>(null);

  // MT5 login form — operator enters credentials on Control Center UI
  const [loginId, setLoginId] = useState('');
  const [loginPw, setLoginPw] = useState('');
  const [loginSrv, setLoginSrv] = useState('');
  const [terminalPath, setTerminalPath] = useState('');
  const [deploySymbol, setDeploySymbol] = useState('XAUUSDm');
  const [deployTf, setDeployTf] = useState('M15');
  const [deployLog, setDeployLog] = useState<string | null>(null);

  // AI provider test
  const [aiTestKeyType, setAiTestKeyType] = useState('openai');
  const [aiTestModel, setAiTestModel] = useState('');
  const [aiTestUrl, setAiTestUrl] = useState('');
  const [aiTestResult, setAiTestResult] = useState<{ ok: boolean; message: string; latency_ms?: number; error_code?: string | null } | null>(null);
  const [aiTestBusy, setAiTestBusy] = useState(false);

  // Risk form
  const [riskFrac, setRiskFrac] = useState(0.01);
  const [maxPos, setMaxPos] = useState(5);
  const [maxSpr, setMaxSpr] = useState(0.5);

  const [aiTestKeyValue, setAiTestKeyValue] = useState('');

  // Telegram form
  const [teleToken, setTeleToken] = useState('');
  const [teleChatId, setTeleChatId] = useState('');
  const [teleEnabled, setTeleEnabled] = useState(true);

  // AI Engine form
  const [activeAiModel, setActiveAiModel] = useState('deepseek-v4-flash-free');
  const [customModelId, setCustomModelId] = useState('');
  const [geminiKey, setGeminiKey] = useState('');
  const [claudeKey, setClaudeKey] = useState('');
  const [deepseekKey, setDeepseekKey] = useState('');
  const [openaiKey, setOpenaiKey] = useState('');
  const [zplayKey, setZplayKey] = useState('');
  const [grokKey, setGrokKey] = useState('');
  const [qwenKey, setQwenKey] = useState('');
  const [gatewayUrl, setGatewayUrl] = useState('');
  const [gatewayKey, setGatewayKey] = useState('');

  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const showToast = useCallback((msg: string, err = false) => {
    if (toastTimer.current) clearTimeout(toastTimer.current);
    setToast({ msg, err });
    toastTimer.current = setTimeout(() => setToast(null), 4000);
  }, []);

  // Poll status while open
  useEffect(() => {
    if (!open) return;
    const ctrl = new AbortController();
    const refresh = async () => {
      try {
        const snap = await fetchControlCenterStatus({ signal: ctrl.signal });
        const aiCfg = await fetchAIConfig();
        if (ctrl.signal.aborted) return;
        if (snap) {
          setCc(snap);
          setLoadErr(null);
          // Sync inputs from server once
          if (snap.account.login) setLoginId(String(snap.account.login));
          if (snap.account.server) setLoginSrv(snap.account.server);
          setRiskFrac((cur) => (cur === 0.01 && snap.risk.risk_per_trade_fraction !== 0.01 ? snap.risk.risk_per_trade_fraction : cur));
          setMaxPos((cur) => (cur === 5 && snap.risk.max_open_positions !== 5 ? snap.risk.max_open_positions : cur));
          if (snap.risk.max_spread != null) setMaxSpr((cur) => (cur === 0.5 && snap.risk.max_spread !== 0.5 ? snap.risk.max_spread! : cur));
          if (snap.telegram) {
            setTeleToken((cur) => (cur === '' && snap.telegram?.bot_token ? snap.telegram.bot_token : cur));
            setTeleChatId((cur) => (cur === '' && snap.telegram?.chat_id ? snap.telegram.chat_id : cur));
            setTeleEnabled((cur) => (snap.telegram?.enabled !== undefined ? snap.telegram.enabled : cur));
          }
          if (aiCfg) {
            if (aiCfg.active_model) setActiveAiModel(aiCfg.active_model);
            if (aiCfg.custom_model_id) setCustomModelId((cur) => (cur === '' ? aiCfg.custom_model_id! : cur));
            if (aiCfg.gemini_api_key) setGeminiKey((cur) => (cur === '' ? aiCfg.gemini_api_key! : cur));
            if (aiCfg.claude_api_key) setClaudeKey((cur) => (cur === '' ? aiCfg.claude_api_key! : cur));
            if (aiCfg.deepseek_api_key) setDeepseekKey((cur) => (cur === '' ? aiCfg.deepseek_api_key! : cur));
            if (aiCfg.openai_api_key) setOpenaiKey((cur) => (cur === '' ? aiCfg.openai_api_key! : cur));
            if (aiCfg.zplay_api_key) setZplayKey((cur) => (cur === '' ? aiCfg.zplay_api_key! : cur));
            if (aiCfg.grok_api_key) setGrokKey((cur) => (cur === '' ? aiCfg.grok_api_key! : cur));
            if (aiCfg.qwen_api_key) setQwenKey((cur) => (cur === '' ? aiCfg.qwen_api_key! : cur));
            if (aiCfg.gateway_url) setGatewayUrl((cur) => (cur === '' ? aiCfg.gateway_url! : cur));
            if (aiCfg.gateway_key) setGatewayKey((cur) => (cur === '' ? aiCfg.gateway_key! : cur));
          }
        } else if (!ctrl.signal.aborted) {
          setLoadErr('Không thể tải Control Center. Kiểm tra API server (port 8005).');
        }
      } catch {
        // Silently ignore aborted requests on unmount/close
      }
    };
    void refresh();
    const t = setInterval(refresh, 4000);

    const stream = createStreamSocket((ev) => {
      if (ev.type === 'config_updated') void refresh();
    });

    return () => {
      ctrl.abort();
      clearInterval(t);
      stream.close();
    };
  }, [open]);

  // Escape to close
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
        triggerRef.current?.focus();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose, triggerRef]);

  if (!open) return null;

  const locked = cc?.execution?.execution_locked ?? true;
  const killActive = cc?.safeguards?.kill_switch_active ?? false;
  const demoArmed = cc?.safeguards?.demo_armed ?? false;
  const aiLoop = cc?.safeguards?.ai_auto_loop ?? false;
  const mode = cc?.execution?.mode ?? 'DISABLED';

  const run = async (key: string, fn: () => Promise<boolean>, okMsg: string) => {
    setBusy(key);
    const ok = await fn();
    setBusy(null);
    if (ok) {
      showToast(okMsg);
      const snap = await fetchControlCenterStatus();
      if (snap) setCc(snap);
    } else {
      showToast('Thao tác thất bại — kiểm tra API server.', true);
    }
  };

  const handleMode = (m: string) =>
    run(`mode-${m}`, async () => (await updateControlMode(m)) !== null, `Execution mode → ${m}`);

  const handleKill = () =>
    run('kill', async () => (await updateControlKillSwitch(!killActive)) !== null, killActive ? 'Kill switch OFF' : 'KILL SWITCH ON — mọi execution bị chặn');

  const handleArm = () =>
    run('arm', async () => (await updateControlDemoArm(!demoArmed)) !== null, demoArmed ? 'Demo DISARMED' : 'Demo ARMED');

  const handleAiLoop = () =>
    run('ailoop', async () => (await updateAiAutoLoop(!aiLoop)) !== null, aiLoop ? 'AI Auto-Loop OFF' : 'AI AUTO-LOOP ON — AI tự sinh lệnh qua Risk Gate');

  const handleLogin = async () => {
    if (!loginId || !loginPw || !loginSrv) {
      showToast('Điền đủ Login / Password / Server.', true);
      return;
    }
    setBusy('login');
    setDeployLog(null);
    const res = await loginMT5Account(parseInt(loginId, 10), loginPw, loginSrv, {
      terminal_path: terminalPath.trim() || undefined,
      symbol: deploySymbol.trim() || undefined,
      timeframe: deployTf.trim() || undefined,
      auto_deploy: true,
    });
    setBusy(null);
    if (res.status === 'SUCCESS') {
      showToast(res.message || 'Đăng nhập MT5 thành công.');
      if (res.symbol) {
        showToast(`Symbol: ${res.symbol.requested} -> ${res.symbol.resolved} (${res.symbol.reason})`);
      }
      if (res.deploy) {
        const lines = (res.deploy.steps || []).map(
          (s: { name: string; ok: boolean; message: string }) => `[${s.ok ? 'OK' : '!!'}] ${s.name}: ${s.message}`,
        );
        setDeployLog(lines.join('\n') || 'Deploy hoàn tất.');
      }
      const snap = await fetchControlCenterStatus();
      if (snap) setCc(snap);
    } else {
      showToast(res.message || 'Đăng nhập MT5 thất bại.', true);
    }
  };

  const handleSaveRisk = async () => {
    setBusy('risk');
    const res = await updateControlRisk(riskFrac, maxPos, maxSpr);
    setBusy(null);
    if (res) {
      showToast(`Risk Guard đã lưu: ${(riskFrac * 100).toFixed(2)}% / trade · ${maxPos} pos · spread ≤ ${maxSpr}`);
      const snap = await fetchControlCenterStatus();
      if (snap) setCc(snap);
    } else {
      showToast('Lưu Risk Guard thất bại.', true);
    }
  };

  const handleTestAI = async () => {
    if (!aiTestModel.trim()) {
      showToast('Nhập model ID cần test trước.', true);
      return;
    }
    setAiTestBusy(true);
    setAiTestResult(null);
    const keyForTest =
      aiTestKeyType === 'gemini' && !aiTestKeyValue.trim() ? geminiKey :
      aiTestKeyType === 'claude' && !aiTestKeyValue.trim() ? claudeKey :
      aiTestKeyType === 'deepseek' && !aiTestKeyValue.trim() ? deepseekKey :
      aiTestKeyType === 'openai' && !aiTestKeyValue.trim() ? openaiKey :
      aiTestKeyType === 'zplay' && !aiTestKeyValue.trim() ? zplayKey :
      aiTestKeyType === 'grok' && !aiTestKeyValue.trim() ? grokKey :
      aiTestKeyType === 'qwen' && !aiTestKeyValue.trim() ? qwenKey :
      aiTestKeyValue;
    const urlForTest =
      aiTestKeyType === 'gemini' && !aiTestUrl.trim() ? '' :
      aiTestKeyType === 'claude' && !aiTestUrl.trim() ? '' :
      aiTestKeyType === 'gateway' ? gatewayUrl : aiTestUrl;
    const res = await testAIConnection({
      key_type: aiTestKeyType,
      api_key: keyForTest,
      model: aiTestModel.trim(),
      base_url: urlForTest || undefined,
    });
    setAiTestBusy(false);
    if (res && res.result) {
      setAiTestResult(res.result);
      showToast(res.result.ok ? `AI OK! ${res.result.latency_ms ?? ''}ms` : `Lỗi: ${res.result.message}`, !res.result.ok);
    } else {
      setAiTestResult({ ok: false, message: 'Không nhận được kết quả test (kiểm tra token đăng nhập).' });
      showToast('Không test được. Có thể phiên đăng nhập đã hết hạn.', true);
    }
  };

  const handleSaveTelegram = async () => {
    setBusy('telegram');
    const res = await updateTelegramConfig(teleToken, teleChatId, teleEnabled);
    setBusy(null);
    if (res && res.status === 'SUCCESS') {
      showToast(res.message);
      const snap = await fetchControlCenterStatus();
      if (snap) setCc(snap);
    } else {
      showToast('Lưu cấu hình Telegram thất bại.', true);
    }
  };

  const handleSaveAIConfig = async () => {
    setBusy('ai_config');
    const res = await updateAIConfig({
      active_model: activeAiModel,
      custom_model_id: customModelId,
      gemini_api_key: geminiKey,
      claude_api_key: claudeKey,
      deepseek_api_key: deepseekKey,
      openai_api_key: openaiKey,
      zplay_api_key: zplayKey,
      grok_api_key: grokKey,
      qwen_api_key: qwenKey,
      gateway_url: gatewayUrl,
      gateway_key: gatewayKey,
    });
    setBusy(null);
    if (res && res.status === 'SUCCESS') {
      showToast(res.message);
      const snap = await fetchControlCenterStatus();
      if (snap) setCc(snap);
    } else {
      showToast('Lưu cấu hình AI Engine thất bại.', true);
    }
  };

  const getCardStyle = (id: string): CSSProperties => ({
    ...card,
    ...(hoveredCard === id ? cardHover : {}),
  });

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="cc-title"
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onClose();
          triggerRef.current?.focus();
        }
      }}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 100,
        background: 'rgba(3,6,12,0.85)',
        backdropFilter: 'blur(8px)',
        WebkitBackdropFilter: 'blur(8px)',
        display: 'flex',
        justifyContent: 'flex-end',
        animation: 'ccFadeIn 0.25s ease',
      }}
    >
      <style>{`
        @keyframes ccFadeIn { from { opacity: 0 } to { opacity: 1 } }
        @keyframes ccSlideIn { from { transform: translateX(50px); opacity: 0 } to { transform: translateX(0); opacity: 1 } }
        @keyframes ccSpin { to { transform: rotate(360deg) } }
        @keyframes ccPulse { 0%, 100% { opacity: 1 } 50% { opacity: 0.5 } }
        .cc-input:focus { border-color: ${C.gold} !important; box-shadow: 0 0 0 3px rgba(212,180,131,0.15); }
        .cc-btn { transition: all 0.2s ease; }
        .cc-btn:hover:not(:disabled) { transform: translateY(-1px); filter: brightness(1.1); }
        .cc-btn:active:not(:disabled) { transform: translateY(0); }
        .cc-btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .cc-card { transition: all 0.2s ease; }
        .cc-card:hover { border-color: ${C.borderGold}; box-shadow: 0 4px 24px rgba(0,0,0,0.35); }
      `}</style>

      <section
        style={{
          width: 'min(680px, 100%)',
          height: '100%',
          overflowY: 'auto',
          background: `linear-gradient(180deg, ${C.bg} 0%, #060810 100%)`,
          borderLeft: `1px solid ${C.borderGold}`,
          boxShadow: '-24px 0 80px rgba(0,0,0,0.7)',
          padding: '24px 28px 48px',
          color: C.text,
          animation: 'ccSlideIn 0.3s ease',
        }}
      >
        {/* ── Header ── */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16 }}>
          <div>
            <h2 id="cc-title" style={{ margin: 0, color: C.gold, fontFamily: C.mono, fontSize: 20, fontWeight: 800, letterSpacing: '0.06em' }}>
              ANH TÚ CONTROL CENTER
            </h2>
            <p style={{ margin: '6px 0 0', color: C.muted, fontSize: 11, fontFamily: C.sans }}>
              Risk Engine · Execution Safeguards · MT5 Bridge
            </p>
          </div>
          <button
            type="button"
            onClick={() => {
              onClose();
              triggerRef.current?.focus();
            }}
            aria-label="Đóng Control Center"
            className="cc-btn"
            style={{
              width: 36,
              height: 36,
              borderRadius: 8,
              background: 'rgba(255,255,255,0.05)',
              border: `1px solid ${C.border}`,
              color: C.dim,
              cursor: 'pointer',
              fontSize: 18,
              display: 'grid',
              placeItems: 'center',
              flexShrink: 0,
            }}
          >
            ×
          </button>
        </div>

        {/* ── Master status banner ── */}
        <div
          role="status"
          aria-live="polite"
          style={{
            marginTop: 20,
            padding: '16px 18px',
            borderRadius: 12,
            background: locked
              ? `linear-gradient(135deg, ${C.redDim}, rgba(244,63,94,0.05))`
              : `linear-gradient(135deg, ${C.greenDim}, rgba(34,211,160,0.05))`,
            border: `1px solid ${locked ? 'rgba(244,63,94,0.4)' : 'rgba(34,211,160,0.4)'}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 24, animation: locked ? 'none' : 'ccPulse 2s infinite' }}>{locked ? '🔒' : '⚡'}</span>
            <div>
              <div style={{ fontSize: 13, fontWeight: 800, fontFamily: C.mono, color: locked ? C.red : C.green, letterSpacing: '0.05em' }}>
                {locked ? 'EXECUTION LOCKED' : 'EXECUTION ARMED'}
              </div>
              <div style={{ fontSize: 10, color: C.dim, fontFamily: C.sans, marginTop: 2 }}>
                {locked ? 'Hệ thống đang ở chế độ an toàn / giám sát.' : 'Hệ thống sẵn sàng thực thi lệnh.'}
              </div>
            </div>
          </div>
          <span
            style={{
              fontSize: 10,
              fontWeight: 800,
              fontFamily: C.mono,
              padding: '6px 12px',
              borderRadius: 6,
              background: 'rgba(0,0,0,0.4)',
              color: locked ? C.red : C.green,
              border: `1px solid ${locked ? 'rgba(244,63,94,0.4)' : 'rgba(34,211,160,0.4)'}`,
              letterSpacing: '0.05em',
            }}
          >
            {cc?.readiness?.reason_code || 'LOADING'}
          </span>
        </div>

        {loadErr && <Toast msg={loadErr} err />}
        {!cc && !loadErr && (
          <div style={{ marginTop: 20, color: C.muted, fontSize: 12, fontFamily: C.mono, display: 'flex', alignItems: 'center', gap: 10 }}>
            <Spinner /> Đang tải diagnostics…
          </div>
        )}

        {cc && (
          <div style={{ display: 'grid', gap: 16, marginTop: 20 }}>
            {/* ── 1. Execution mode & safeguards ── */}
            <div
              className="cc-card"
              style={getCardStyle('mode')}
              onMouseEnter={() => setHoveredCard('mode')}
              onMouseLeave={() => setHoveredCard(null)}
            >
              <SectionHeader num="1" title="EXECUTION MODE & SAFEGUARDS" sub="Chọn chế độ vận hành và công tắc an toàn tổng." />

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
                {(['DEMO', 'LIVE', 'DISABLED'] as const).map((m) => {
                  const active = mode === m;
                  const col = m === 'LIVE' ? C.red : m === 'DEMO' ? C.green : C.muted;
                  return (
                    <button
                      key={m}
                      type="button"
                      disabled={busy !== null}
                      onClick={() => handleMode(m)}
                      className="cc-btn"
                      style={{
                        ...btnBase,
                        padding: '12px 0',
                        fontSize: 11,
                        background: active ? `${col}20` : 'rgba(0,0,0,0.3)',
                        border: `1.5px solid ${active ? col : C.border}`,
                        color: active ? col : C.muted,
                        boxShadow: active ? `0 0 20px ${col}25` : 'none',
                      }}
                    >
                      {busy === `mode-${m}` ? <Spinner /> : null}
                      {m === 'LIVE' ? '🔴 LIVE' : m === 'DEMO' ? '🟢 DEMO' : '⚪ DISABLED'}
                    </button>
                  );
                })}
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 14 }}>
                <div
                  style={{
                    padding: '14px 16px',
                    borderRadius: 10,
                    background: killActive ? C.redDim : 'rgba(255,255,255,0.02)',
                    border: `1px solid ${killActive ? 'rgba(244,63,94,0.4)' : C.border}`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    transition: 'all 0.2s ease',
                  }}
                >
                  <div>
                    <div style={{ fontSize: 11, fontWeight: 700, fontFamily: C.mono, color: killActive ? C.red : C.text }}>
                      ⛔ KILL SWITCH
                    </div>
                    <div style={{ fontSize: 9, color: C.muted, fontFamily: C.sans, marginTop: 2 }}>
                      {killActive ? 'Đang chặn mọi execution' : 'Hệ thống bình thường'}
                    </div>
                  </div>
                  <ToggleSwitch active={killActive} onChange={handleKill} disabled={busy !== null} activeColor={C.red} />
                </div>

                <div
                  style={{
                    padding: '14px 16px',
                    borderRadius: 10,
                    background: demoArmed ? C.goldDim : 'rgba(255,255,255,0.02)',
                    border: `1px solid ${demoArmed ? C.borderGold : C.border}`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    transition: 'all 0.2s ease',
                  }}
                >
                  <div>
                    <div style={{ fontSize: 11, fontWeight: 700, fontFamily: C.mono, color: demoArmed ? C.gold : C.text }}>
                      🎯 DEMO ARM
                    </div>
                    <div style={{ fontSize: 9, color: C.muted, fontFamily: C.sans, marginTop: 2 }}>
                      {demoArmed ? 'Sẵn sàng thực thi demo' : 'Chưa arm demo'}
                    </div>
                  </div>
                  <ToggleSwitch active={demoArmed} onChange={handleArm} disabled={busy !== null} activeColor={C.gold} />
                </div>

                <div
                  style={{
                    padding: '14px 16px',
                    borderRadius: 10,
                    background: aiLoop ? C.greenDim : 'rgba(255,255,255,0.02)',
                    border: `1px solid ${aiLoop ? 'rgba(34,211,160,0.4)' : C.border}`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    transition: 'all 0.2s ease',
                  }}
                >
                  <div>
                    <div style={{ fontSize: 11, fontWeight: 700, fontFamily: C.mono, color: aiLoop ? C.green : C.text }}>
                      AI AUTO-LOOP
                    </div>
                    <div style={{ fontSize: 9, color: C.muted, fontFamily: C.sans, marginTop: 2 }}>
                      {aiLoop ? 'AI tự sinh lệnh qua Risk Gate' : 'AI chỉ phân tích'}
                    </div>
                  </div>
                  <ToggleSwitch active={aiLoop} onChange={handleAiLoop} disabled={busy !== null} activeColor={C.green} />
                </div>
              </div>
            </div>

            {/* ── 2. MT5 authentication ── */}
            <div
              className="cc-card"
              style={getCardStyle('mt5')}
              onMouseEnter={() => setHoveredCard('mt5')}
              onMouseLeave={() => setHoveredCard(null)}
            >
              <SectionHeader num="2" title="MT5 ACCOUNT CONNECTION" sub="Đăng nhập lại tài khoản MT5 mà không cần restart server." />

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
                <div>
                  <label style={label}>Login ID</label>
                  <input className="cc-input" type="number" value={loginId} onChange={(e) => setLoginId(e.target.value)} style={input} />
                </div>
                <div>
                  <label style={label}>Password</label>
                  <input className="cc-input" type="password" value={loginPw} onChange={(e) => setLoginPw(e.target.value)} style={input} />
                </div>
                <div>
                  <label style={label}>Server</label>
                  <input className="cc-input" type="text" value={loginSrv} onChange={(e) => setLoginSrv(e.target.value)} style={input} />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1.5fr', gap: 10, marginTop: 10 }}>
                <div>
                  <label style={label}>Symbol (Subscribe)</label>
                  <input className="cc-input" type="text" value={deploySymbol} onChange={(e) => setDeploySymbol(e.target.value)} style={input} placeholder="XAUUSDm" />
                  <div style={{ fontSize: 9, color: C.muted, fontFamily: C.mono, marginTop: 4 }}>tự fallback XAUUSD nếu không có</div>
                </div>
                <div>
                  <label style={label}>Timeframe</label>
                  <select className="cc-input" value={deployTf} onChange={(e) => setDeployTf(e.target.value)} style={{ ...input, background: '#0d111a', color: C.gold, cursor: 'pointer' }}>
                    {['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1', 'W1'].map((tf) => (
                      <option key={tf} value={tf}>{tf}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label style={label}>Auto deploy EA</label>
                  <input className="cc-input" type="text" value="ON" disabled style={{ ...input, color: C.green, fontWeight: 700 }} />
                  <div style={{ fontSize: 9, color: C.muted, fontFamily: C.mono, marginTop: 4 }}>mở MT5 → gắn .ex5 → bật Algo Trading</div>
                </div>
                <div>
                  <label style={label}>Terminal64 Path (để trống = tự dò)</label>
                  <input
                    className="cc-input"
                    type="text"
                    value={terminalPath}
                    onChange={(e) => setTerminalPath(e.target.value)}
                    style={{ ...input, color: C.blue }}
                    placeholder="C:\Program Files\...\terminal64.exe"
                  />
                </div>
              </div>

              {deployLog && (
                <pre
                  style={{
                    marginTop: 12,
                    padding: '10px 12px',
                    background: 'rgba(0,0,0,0.45)',
                    border: `1px solid ${C.border}`,
                    borderRadius: 8,
                    fontFamily: C.mono,
                    fontSize: 10,
                    color: C.dim,
                    whiteSpace: 'pre-wrap',
                    maxHeight: 160,
                    overflowY: 'auto',
                  }}
                >{deployLog}</pre>
              )}

              <button
                type="button"
                onClick={handleLogin}
                disabled={busy !== null}
                className="cc-btn"
                style={{
                  ...btnBase,
                  width: '100%',
                  marginTop: 12,
                  padding: '12px 0',
                  background: `linear-gradient(135deg, ${C.blueDim}, rgba(56,189,248,0.05))`,
                  border: `1.5px solid ${C.blue}`,
                  color: C.blue,
                  fontSize: 12,
                }}
              >
                {busy === 'login' ? <Spinner /> : '🔑 '}
                {busy === 'login' ? 'ĐANG KẾT NỐI MT5…' : 'KẾT NỐI / ĐĂNG NHẬP MT5'}
              </button>

              <div
                style={{
                  marginTop: 12,
                  display: 'grid',
                  gridTemplateColumns: 'repeat(4, 1fr)',
                  gap: 8,
                  background: 'rgba(0,0,0,0.35)',
                  padding: '12px 14px',
                  borderRadius: 10,
                  border: `1px solid ${C.border}`,
                }}
              >
                {[
                  ['LOGIN', String(cc.account.login ?? '—'), C.gold],
                  ['SERVER', cc.account.server ?? '—', C.text],
                  ['TYPE', cc.account.trade_mode ?? '—', cc.account.trade_mode === 'DEMO' ? C.green : C.red],
                  ['LEVERAGE', cc.account.leverage ? `1:${cc.account.leverage}` : '—', C.text],
                ].map(([k, v, col]) => (
                  <div key={k as string}>
                    <div style={{ fontSize: 8, color: C.muted, fontFamily: C.mono, letterSpacing: '0.1em' }}>{k}</div>
                    <div style={{ fontSize: 11, color: col as string, fontFamily: C.mono, fontWeight: 700, marginTop: 3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{v}</div>
                  </div>
                ))}
              </div>

              <div style={{ marginTop: 10, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <StatusPill ok={cc.account.mt5_connected} labelOk="MT5 CONNECTED" labelBad="MT5 DISCONNECTED" />
                <StatusPill ok={cc.account.identity_matches_expected} labelOk="IDENTITY MATCH" labelBad="IDENTITY MISMATCH" />
                <StatusPill ok={cc.safeguards.bridge_auth_configured} labelOk="BRIDGE AUTH OK" labelBad="BRIDGE AUTH MISSING" />
              </div>
            </div>

            {/* ── 3. Risk guard ── */}
            <div
              className="cc-card"
              style={getCardStyle('risk')}
              onMouseEnter={() => setHoveredCard('risk')}
              onMouseLeave={() => setHoveredCard(null)}
            >
              <SectionHeader num="3" title="RISK GUARD CONFIGURATOR" sub="Giới hạn rủi ro áp dụng cho mọi lệnh do AI / EA đề xuất." />

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
                <div>
                  <label style={label}>Risk / Trade (fraction)</label>
                  <input
                    className="cc-input"
                    type="number"
                    step="0.001"
                    min="0.0001"
                    max="0.05"
                    value={riskFrac}
                    onChange={(e) => setRiskFrac(parseFloat(e.target.value) || 0.001)}
                    style={input}
                  />
                  <div style={{ fontSize: 9, color: C.gold, fontFamily: C.mono, marginTop: 4 }}>= {(riskFrac * 100).toFixed(2)}% equity</div>
                </div>
                <div>
                  <label style={label}>Max Positions</label>
                  <input
                    className="cc-input"
                    type="number"
                    min="1"
                    max="10"
                    value={maxPos}
                    onChange={(e) => setMaxPos(parseInt(e.target.value, 10) || 1)}
                    style={input}
                  />
                  <div style={{ fontSize: 9, color: C.muted, fontFamily: C.mono, marginTop: 4 }}>lệnh mở đồng thời</div>
                </div>
                <div>
                  <label style={label}>Max Spread</label>
                  <input
                    className="cc-input"
                    type="number"
                    step="0.05"
                    min="0.1"
                    max="5.0"
                    value={maxSpr}
                    onChange={(e) => setMaxSpr(parseFloat(e.target.value) || 0.5)}
                    style={input}
                  />
                  <div style={{ fontSize: 9, color: C.muted, fontFamily: C.mono, marginTop: 4 }}>USD (XAUUSD)</div>
                </div>
              </div>

              <button
                type="button"
                onClick={handleSaveRisk}
                disabled={busy !== null}
                className="cc-btn"
                style={{
                  ...btnBase,
                  width: '100%',
                  marginTop: 12,
                  padding: '12px 0',
                  background: `linear-gradient(135deg, ${C.greenDim}, rgba(34,211,160,0.05))`,
                  border: `1.5px solid ${C.green}`,
                  color: C.green,
                  fontSize: 12,
                }}
              >
                {busy === 'risk' ? <Spinner /> : '💾 '}
                LƯU CẤU HÌNH RISK GUARD
              </button>

              <div style={{ marginTop: 12 }}>
                <KV k="Policy version" v={cc.risk.policy_version} />
                <KV k="Risk profile" v={cc.risk.profile_found ? 'LOADED' : 'MISSING'} color={cc.risk.profile_found ? C.green : C.red} />
                <KV k="Risk per trade (server)" v={`${(cc.risk.risk_per_trade_fraction * 100).toFixed(2)}%`} color={C.gold} />
                <KV k="Max daily loss" v={`${(cc.risk.max_daily_loss_fraction * 100).toFixed(1)}%`} color={C.red} />
              </div>
            </div>

            {/* ── 4. Telegram notification bot ── */}
            <div
              className="cc-card"
              style={getCardStyle('telegram')}
              onMouseEnter={() => setHoveredCard('telegram')}
              onMouseLeave={() => setHoveredCard(null)}
            >
              <SectionHeader num="4" title="TELEGRAM NOTIFICATIONS BOT" sub="Nhận thông báo tín hiệu AI, vào lệnh & quản trị rủi ro trực tiếp qua Telegram." />

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                <div>
                  <label style={label}>Telegram Bot Token</label>
                  <input
                    className="cc-input"
                    type="password"
                    placeholder="ví dụ: 7890123456:AA..."
                    value={teleToken}
                    onChange={(e) => setTeleToken(e.target.value)}
                    style={input}
                  />
                </div>
                <div>
                  <label style={label}>Telegram Chat ID</label>
                  <input
                    className="cc-input"
                    type="text"
                    placeholder="ví dụ: 123456789"
                    value={teleChatId}
                    onChange={(e) => setTeleChatId(e.target.value)}
                    style={input}
                  />
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 10 }}>
                <span style={{ fontSize: 10, color: C.dim, fontFamily: C.sans }}>Bật thông báo Telegram realtime khi AI sinh lệnh</span>
                <ToggleSwitch active={teleEnabled} onChange={() => setTeleEnabled(!teleEnabled)} activeColor={C.blue} />
              </div>

              <button
                type="button"
                onClick={handleSaveTelegram}
                disabled={busy !== null}
                className="cc-btn"
                style={{
                  ...btnBase,
                  width: '100%',
                  marginTop: 12,
                  padding: '12px 0',
                  background: `linear-gradient(135deg, ${C.blueDim}, rgba(56,189,248,0.05))`,
                  border: `1.5px solid ${C.blue}`,
                  color: C.blue,
                  fontSize: 12,
                }}
              >
                {busy === 'telegram' ? <Spinner /> : 'KẾT NỐI & TEST GỬI TIN TELEGRAM'}
              </button>
            </div>

            {/* ── 5. Multi-AI provider & model configurator ── */}
            <div
              className="cc-card"
              style={getCardStyle('ai_engine')}
              onMouseEnter={() => setHoveredCard('ai_engine')}
              onMouseLeave={() => setHoveredCard(null)}
            >
              <SectionHeader
                num="5"
                title="AI PROVIDER & MULTI-MODEL ENGINE"
                sub="Mặc định dùng model FREE của OpenCode Zen (không cần key). Nhập API key/model/gateway riêng để ưu tiên hơn model mặc định; tự động đổi model khi hết token/lỗi."
              />

              <div style={{ marginBottom: 12 }}>
                <label style={label}>Mô hình AI Ưu tiên (Selected Primary Model)</label>
                <select
                  className="cc-input"
                  value={activeAiModel}
                  onChange={(e) => setActiveAiModel(e.target.value)}
                  style={{
                    ...input,
                    background: '#0d111a',
                    color: C.gold,
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  <optgroup label="🆓 OpenCode Zen Free (Mặc định - Không cần API Key)">
                    <option value="deepseek-v4-flash-free">OpenCode DeepSeek V4 Flash Free ⭐ (Mặc định)</option>
                    <option value="big-pickle">OpenCode Big Pickle Free (Reasoning)</option>
                    <option value="mimo-v2.5-free">OpenCode MiMo V2.5 Free</option>
                    <option value="nemotron-3-ultra-free">OpenCode Nemotron 3 Ultra Free</option>
                    <option value="north-mini-code-free">OpenCode North Mini Code Free</option>
                    <option value="laguna-s-2.1-free">OpenCode Laguna S 2.1 Free</option>
                    <option value="longcat-2.0-free">OpenCode LongCat 2.0 Free</option>
                    <option value="ling-3.0-flash-free">OpenCode Ling 3.0 Flash Free (Deprecated)</option>
                  </optgroup>

                  <optgroup label="✨ OpenAI (GPT-5.6 / GPT-5.x / o-Series)">
                    <option value="gpt-5.6-sol">OpenAI GPT-5.6 Sol ⭐ (Flagship 07/2026)</option>
                    <option value="gpt-5.6-terra">OpenAI GPT-5.6 Terra</option>
                    <option value="gpt-5.6-luna">OpenAI GPT-5.6 Luna</option>
                    <option value="gpt-5.5">OpenAI GPT-5.5 / GPT-5.5 Pro</option>
                    <option value="gpt-5.4">OpenAI GPT-5.4 / Mini / Nano</option>
                    <option value="gpt-5">OpenAI GPT-5 / Mini / Nano</option>
                    <option value="o3">OpenAI o3 (Reasoning)</option>
                    <option value="o3-pro">OpenAI o3 Pro</option>
                    <option value="o4-mini">OpenAI o4 Mini</option>
                    <option value="gpt-4.1">OpenAI GPT-4.1 / Mini</option>
                    <option value="gpt-4o">OpenAI GPT-4o</option>
                    <option value="gpt-4o-mini">OpenAI GPT-4o Mini</option>
                  </optgroup>

                  <optgroup label="👑 Anthropic (Claude 5 / Claude 4.x / 3.x)">
                    <option value="claude-5-fable">Claude Fable 5 ⭐ (Flagship)</option>
                    <option value="claude-5-mythos">Claude Mythos 5 (Limited)</option>
                    <option value="claude-5-opus">Claude Opus 5</option>
                    <option value="claude-5-sonnet">Claude Sonnet 5</option>
                    <option value="claude-4.8-opus">Claude Opus 4.8 / 4.7 / 4.6</option>
                    <option value="claude-4.6-sonnet">Claude Sonnet 4.6 / 4.5</option>
                    <option value="claude-4.5-haiku">Claude Haiku 4.5</option>
                    <option value="claude-3.7-sonnet">Claude 3.7 Sonnet</option>
                    <option value="claude-3-5-sonnet">Claude 3.5 Sonnet</option>
                  </optgroup>

                  <optgroup label="⚡ Google DeepMind (Gemini 3.x / 2.x)">
                    <option value="gemini-3.6-flash">Google Gemini 3.6 Flash ⭐ (Mới nhất)</option>
                    <option value="gemini-3.5-flash">Google Gemini 3.5 Flash / Lite</option>
                    <option value="gemini-3.1-pro">Google Gemini 3.1 Pro / Lite</option>
                    <option value="gemini-3-pro">Google Gemini 3 Pro / Flash</option>
                    <option value="gemini-2.5-pro">Google Gemini 2.5 Pro / Flash</option>
                    <option value="gemini-2.0-flash">Google Gemini 2.0 Flash</option>
                    <option value="gemini-1.5-pro">Google Gemini 1.5 Pro</option>
                  </optgroup>

                  <optgroup label="🔮 DeepSeek">
                    <option value="deepseek-v4-pro">DeepSeek V4 Pro ⭐</option>
                    <option value="deepseek-v4-flash">DeepSeek V4 Flash (0731)</option>
                    <option value="deepseek-v3.2">DeepSeek V3.2 / V3.1 / V3</option>
                    <option value="deepseek-r1">DeepSeek R1 (Thinking Mode)</option>
                  </optgroup>

                  <optgroup label="🚀 xAI (Grok)">
                    <option value="grok-4.5">xAI Grok 4.5 ⭐ (Flagship)</option>
                    <option value="grok-4">xAI Grok 4 / 4.3 / 4.20</option>
                    <option value="grok-4-fast">xAI Grok 4 Fast / 4.1 Fast</option>
                    <option value="grok-3">xAI Grok 3 / 3 Mini</option>
                  </optgroup>

                  <optgroup label="🌙 Moonshot AI (Kimi) & Alibaba Qwen">
                    <option value="kimi-k3">Moonshot Kimi K3 ⭐</option>
                    <option value="kimi-k2.6">Moonshot Kimi K2.6 / K2 Thinking</option>
                    <option value="qwen3.8-max">Alibaba Qwen3.8 Max ⭐</option>
                    <option value="qwen3-thinking">Alibaba Qwen3 Thinking / Coder / VL</option>
                  </optgroup>

                  <optgroup label="🌐 Zhipu GLM / MiniMax / Meta Llama / Mistral">
                    <option value="glm-5.2">Zhipu GLM-5.2 ⭐ / GLM-4.7 Flash</option>
                    <option value="minimax-m3">MiniMax M3 ⭐ / M1</option>
                    <option value="llama-4-maverick">Meta Llama 4 Maverick ⭐ / Scout</option>
                    <option value="magistral-medium">Mistral Magistral Medium ⭐ / Large</option>
                    <option value="codestral">Mistral Codestral</option>
                  </optgroup>

                  <optgroup label="💡 Open Source & Specialized Models">
                    <option value="phi-4">Microsoft Phi-4 / Mini / Multimodal</option>
                    <option value="command-a">Cohere Command A / R+</option>
                    <option value="jamba-large">AI21 Jamba Large / Mini</option>
                    <option value="nemotron-ultra">NVIDIA Nemotron Ultra</option>
                    <option value="granite-4">IBM Granite 4</option>
                    <option value="gemma-3">Google Gemma 3 / 4</option>
                  </optgroup>
                </select>
              </div>

              <div style={{ marginBottom: 12 }}>
                <label style={label}>Custom Model Name / ID (Gõ model tùy chỉnh nếu không có trong danh sách)</label>
                <input
                  className="cc-input"
                  type="text"
                  placeholder="ví dụ: gpt-5.6-sol, claude-5-fable, deepseek/deepseek-r1, mistralai/mistral-large..."
                  value={customModelId}
                  onChange={(e) => setCustomModelId(e.target.value)}
                  style={{ ...input, color: C.blue }}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginTop: 10 }}>
                <div>
                  <label style={label}>Gemini API Key (Custom)</label>
                  <input
                    className="cc-input"
                    type="password"
                    placeholder="AQ... hoặc sk-..."
                    value={geminiKey}
                    onChange={(e) => setGeminiKey(e.target.value)}
                    style={input}
                  />
                </div>
                <div>
                  <label style={label}>Claude API Key (Custom)</label>
                  <input
                    className="cc-input"
                    type="password"
                    placeholder="sk-ant-..."
                    value={claudeKey}
                    onChange={(e) => setClaudeKey(e.target.value)}
                    style={input}
                  />
                </div>
                <div>
                  <label style={label}>DeepSeek API Key (Custom)</label>
                  <input
                    className="cc-input"
                    type="password"
                    placeholder="sk-..."
                    value={deepseekKey}
                    onChange={(e) => setDeepseekKey(e.target.value)}
                    style={input}
                  />
                </div>
                <div>
                  <label style={label}>OpenAI API Key (Custom)</label>
                  <input
                    className="cc-input"
                    type="password"
                    placeholder="sk-proj-..."
                    value={openaiKey}
                    onChange={(e) => setOpenaiKey(e.target.value)}
                    style={input}
                  />
                </div>
                <div>
                  <label style={label}>xAI Grok API Key (Custom)</label>
                  <input
                    className="cc-input"
                    type="password"
                    placeholder="xai-..."
                    value={grokKey}
                    onChange={(e) => setGrokKey(e.target.value)}
                    style={input}
                  />
                </div>
                <div>
                  <label style={label}>ZPlay / Kimi API Key (Custom)</label>
                  <input
                    className="cc-input"
                    type="password"
                    placeholder="sk-e1LJX..."
                    value={zplayKey}
                    onChange={(e) => setZplayKey(e.target.value)}
                    style={input}
                  />
                </div>
              </div>

              {/* ── API Gateway Configuration ── */}
              <div style={{ marginTop: 12, background: 'rgba(56,189,248,0.04)', padding: '10px 12px', borderRadius: 8, border: `1px solid ${C.blueDim}` }}>
                <div style={{ fontSize: 10, color: C.blue, fontFamily: C.mono, fontWeight: 700, marginBottom: 6 }}>
                  🔌 API GATEWAY / ROUTER INTEGRATION (OpenRouter, Together AI, Groq, SiliconFlow, ...)
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                  <div>
                    <label style={label}>Gateway Endpoint Base URL</label>
                    <input
                      className="cc-input"
                      type="text"
                      placeholder="https://openrouter.ai/api/v1 hoặc https://api.together.xyz/v1"
                      value={gatewayUrl}
                      onChange={(e) => setGatewayUrl(e.target.value)}
                      style={input}
                    />
                  </div>
                  <div>
                    <label style={label}>Gateway API Key</label>
                    <input
                      className="cc-input"
                      type="password"
                      placeholder="sk-or-v1-... hoặc custom key"
                      value={gatewayKey}
                      onChange={(e) => setGatewayKey(e.target.value)}
                      style={input}
                    />
                  </div>
                </div>
              </div>

              {/* ── AI Provider Connection Test ── */}
              <div style={{ marginTop: 12, background: 'rgba(34,211,160,0.05)', padding: '10px 12px', borderRadius: 8, border: `1px solid ${C.greenDim}` }}>
                <div style={{ fontSize: 10, color: C.green, fontFamily: C.mono, fontWeight: 700, marginBottom: 6 }}>
                  🧪 TEST KẾT NỐI NHÀ CUNG CẤP AI (key + model + url) — trước khi lưu
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.2fr 1fr', gap: 8 }}>
                  <div>
                    <label style={label}>Provider</label>
                    <select
                      className="cc-input"
                      value={aiTestKeyType}
                      onChange={(e) => { setAiTestKeyType(e.target.value); setAiTestResult(null); }}
                      style={{ ...input, background: '#0d111a', color: C.green, cursor: 'pointer' }}
                    >
                      <option value="openai">OpenAI</option>
                      <option value="gemini">Gemini / Google</option>
                      <option value="claude">Anthropic Claude</option>
                      <option value="deepseek">DeepSeek</option>
                      <option value="zplay">ZPlay / FlatKey</option>
                      <option value="grok">xAI Grok</option>
                      <option value="qwen">Alibaba Qwen</option>
                      <option value="gateway">Custom Gateway (URL bên dưới)</option>
                      <option value="opencode">OpenCode Zen Free</option>
                    </select>
                  </div>
                  <div>
                    <label style={label}>Model ID</label>
                    <input
                      className="cc-input"
                      type="text"
                      placeholder="vd: gpt-4o, gemini-2.5-pro, claude-3-5-sonnet..."
                      value={aiTestModel}
                      onChange={(e) => setAiTestModel(e.target.value)}
                      style={input}
                    />
                  </div>
                  <div>
                    <label style={label}>{aiTestKeyType === 'opencode' ? 'Base URL (tùy chọn)' : 'API Key / Base URL'}</label>
                    <input
                      className="cc-input"
                      type="password"
                      placeholder={aiTestKeyType === 'gateway' ? 'để trống = dùng gateway URL' : 'API key...'}
                      value={aiTestKeyValue}
                      onChange={(e) => setAiTestKeyValue(e.target.value)}
                      style={input}
                    />
                  </div>
                </div>
                {aiTestKeyType === 'gateway' && (
                  <div style={{ marginTop: 6 }}>
                    <label style={label}>Base URL</label>
                    <input
                      className="cc-input"
                      type="text"
                      placeholder="https://openrouter.ai/api/v1"
                      value={aiTestUrl}
                      onChange={(e) => setAiTestUrl(e.target.value)}
                      style={input}
                    />
                  </div>
                )}
                <button
                  type="button"
                  onClick={handleTestAI}
                  disabled={busy !== null || aiTestBusy}
                  className="cc-btn"
                  style={{
                    ...btnBase,
                    width: '100%',
                    marginTop: 10,
                    padding: '10px 0',
                    background: `linear-gradient(135deg, ${C.greenDim}, rgba(34,211,160,0.05))`,
                    border: `1.5px solid ${C.green}`,
                    color: C.green,
                    fontSize: 12,
                  }}
                >
                  {aiTestBusy ? <Spinner /> : '⚡ '}
                  {aiTestBusy ? 'ĐANG TEST…' : 'TEST KẾT NỐI AI' }
                </button>
                {aiTestResult && (
                  <div
                    style={{
                      marginTop: 10,
                      padding: '10px 12px',
                      borderRadius: 8,
                      fontFamily: C.mono,
                      fontSize: 10.5,
                      whiteSpace: 'pre-wrap',
                      lineHeight: 1.5,
                      background: aiTestResult.ok ? 'rgba(34,211,160,0.08)' : 'rgba(244,63,94,0.08)',
                      border: `1px solid ${aiTestResult.ok ? C.green : C.red}`,
                      color: aiTestResult.ok ? C.green : C.red,
                    }}
                  >
                    {aiTestResult.ok ? '✅ KẾT NỐI OK' : `⚠️ LỖI [${aiTestResult.error_code || 'UNKNOWN'}]`}
                    {'\n'}
                    {aiTestResult.message}
                    {aiTestResult.latency_ms ? `\nLatency: ${aiTestResult.latency_ms}ms` : ''}
                  </div>
                )}
              </div>

              <div style={{ marginTop: 10, background: 'rgba(212,180,131,0.06)', padding: '10px 12px', borderRadius: 8, border: `1px solid ${C.borderGold}` }}>
                <div style={{ fontSize: 10, color: C.gold, fontFamily: C.mono, fontWeight: 700 }}>
                  🤖 TỰ ĐỘNG XOAY VÒNG KEY KHI HẾT TOKEN (AUTO TOKEN FAILOVER)
                </div>
                <div style={{ fontSize: 9, color: C.dim, fontFamily: C.sans, marginTop: 4 }}>
                  Khi model ưu tiên bị lỗi (429 Out of Token / Rate Limit / Timeout), hệ thống tự động đổi sang key/model tiếp theo trong hàng đợi (Gateway → User Custom Model → Gemini → OpenAI → FlatKey).
                </div>
              </div>

              <button
                type="button"
                onClick={handleSaveAIConfig}
                disabled={busy !== null}
                className="cc-btn"
                style={{
                  ...btnBase,
                  width: '100%',
                  marginTop: 12,
                  padding: '12px 0',
                  background: `linear-gradient(135deg, ${C.goldDim}, rgba(212,180,131,0.05))`,
                  border: `1.5px solid ${C.gold}`,
                  color: C.gold,
                  fontSize: 12,
                }}
              >
                {busy === 'ai_config' ? <Spinner /> : '🧠 '}
                LƯU CẤU HÌNH AI MODEL & KÍCH HOẠT TOKEN FAILOVER
              </button>
            </div>

            {/* ── 6. Command ledger & data integrity ── */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <div
                className="cc-card"
                style={getCardStyle('ledger')}
                onMouseEnter={() => setHoveredCard('ledger')}
                onMouseLeave={() => setHoveredCard(null)}
              >
                <SectionHeader num="5" title="COMMAND LEDGER" />
                <KV k="Bridge state" v={cc.bridge.status} color={cc.bridge.mt5_connected ? C.green : C.red} />
                <KV k="Pending" v={String(cc.command_ledger.counts.PENDING || 0)} color={C.gold} />
                <KV k="Executed" v={String(cc.command_ledger.counts.EXECUTED || 0)} color={C.green} />
                <KV k="Rejected" v={String(cc.command_ledger.counts.REJECTED || 0)} color={C.red} />
                <KV k="Failed" v={String(cc.command_ledger.counts.FAILED || 0)} color={C.red} />
                <KV k="Last state" v={cc.command_ledger.last_command?.state || 'NONE'} />
              </div>

              <div
                className="cc-card"
                style={getCardStyle('data')}
                onMouseEnter={() => setHoveredCard('data')}
                onMouseLeave={() => setHoveredCard(null)}
              >
                <SectionHeader num="6" title="DATA INTEGRITY" />
                <KV k="MT5 data" v={cc.data_sources.mt5} color={cc.data_sources.mt5 === 'LIVE_VERIFIED' ? C.green : C.gold} />
                <KV k="AI signal" v={cc.data_sources.ai_signal} />
                <KV k="Performance" v={cc.data_sources.performance} />
                <KV k="Snapshot" v={new Date(cc.generated_at).toLocaleTimeString('vi-VN')} />
                <KV k="Symbol" v={cc.execution.symbol} color={C.gold} />
                <KV k="Cmd TTL" v={`${cc.execution.command_ttl_seconds}s`} />
              </div>
            </div>
          </div>
        )}

        {/* Toast stack */}
        {toast && <Toast msg={toast.msg} err={toast.err} />}
      </section>
    </div>
  );
}
