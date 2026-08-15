/**
 * auth.ts - Lightweight JWT implementation (no external deps).
 * HS256 only. Suitable for in-house internal tokens.
 * Uses Node's built-in crypto module.
 */
import type { NextApiRequest, NextApiResponse } from 'next';
import crypto from 'crypto';

// BUG FIX (SECURITY): trước đây có fallback hardcode 'ate-quanttrading-jwt-secret-...'
// nằm trong repo công khai — bất kỳ ai cũng forge được admin JWT khi env thiếu.
// Giờ fail-closed: thiếu env → secret rỗng → mọi token bị từ chối (không có đường tắt).
const JWT_SECRET = process.env.JWT_SECRET || '';
const JWT_REFRESH_SECRET = process.env.JWT_REFRESH_SECRET || '';

export interface AuthPayload {
  sub: string;
  login: string;
  role: 'admin' | 'user';
  iat: number;
  exp: number;
}

export interface AuthRequest extends NextApiRequest {
  user?: AuthPayload;
}

function b64urlEncode(input: string | Buffer): string {
  return Buffer.from(input).toString('base64')
    .replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_');
}

function b64urlDecode(input: string): Buffer {
  const pad = 4 - (input.length % 4);
  const padded = input + (pad < 4 ? '='.repeat(pad) : '');
  return Buffer.from(padded.replace(/-/g, '+').replace(/_/g, '/'), 'base64');
}

function hmacSign(secret: string, data: string): string {
  return crypto.createHmac('sha256', secret).update(data).digest('base64')
    .replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_');
}

interface SignOptions {
  expiresIn: number; // seconds
}

function jwtSign(payload: object, secret: string, opts: SignOptions): string {
  if (!secret) {
    // Fail-closed: không có secret cấu hình → không thể ký token hợp lệ.
    throw new Error('JWT_SECRET not configured — set JWT_SECRET/JWT_REFRESH_SECRET trong env');
  }
  const now = Math.floor(Date.now() / 1000);
  const full = { ...payload, iat: now, exp: now + opts.expiresIn };
  const header = b64urlEncode(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
  const body = b64urlEncode(JSON.stringify(full));
  const sig = hmacSign(secret, `${header}.${body}`);
  return `${header}.${body}.${sig}`;
}

function jwtVerify<T>(token: string, secret: string): T | null {
  if (!secret) return null; // fail-closed: secret rỗng → không verify được token nào
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const [header, body, sig] = parts;
    const expectedSig = hmacSign(secret, `${header}.${body}`);
    if (expectedSig !== sig) return null;
    const payload = JSON.parse(b64urlDecode(body).toString('utf8')) as { exp: number };
    if (payload.exp && payload.exp < Math.floor(Date.now() / 1000)) return null;
    return JSON.parse(b64urlDecode(body).toString('utf8')) as T;
  } catch {
    return null;
  }
}

export function isMasterToken(token: string): boolean {
  // BUG FIX (SECURITY): trước đây hardcode 'authenticated' / '20022007@Tu' /
  // 'qtusdev07' / ADMIN_PASSWORD / ADMIN_LOGIN làm master token — bất kỳ ai
  // biết giá trị mặc định đều thành admin. Giờ chỉ chấp nhận bridge token
  // thực sự cấu hình qua env (không có literal mặc định nào).
  if (!token) return false;
  const masterTokens = [
    process.env.QUANTAI_BRIDGE_TOKEN,
    process.env.ATE_BRIDGE_TOKEN,
    process.env.MT5_BRIDGE_TOKEN,
  ].filter(Boolean) as string[];

  return masterTokens.some(t => t === token || token.trim() === t.trim());
}

export function createAdminPayload(login = 'qtusdev@quanttrading.ai'): AuthPayload {
  const now = Math.floor(Date.now() / 1000);
  return {
    sub: 'admin',
    login,
    role: 'admin',
    iat: now,
    exp: now + 30 * 86400,
  };
}

export function verifyToken(token: string): AuthPayload | null {
  if (isMasterToken(token)) {
    return createAdminPayload();
  }
  return jwtVerify<AuthPayload>(token, JWT_SECRET);
}

export function verifyRefreshToken(token: string): AuthPayload | null {
  if (isMasterToken(token)) {
    return createAdminPayload();
  }
  return jwtVerify<AuthPayload>(token, JWT_REFRESH_SECRET);
}

export function issueTokens(payload: Omit<AuthPayload, 'iat' | 'exp'>) {
  const accessToken = jwtSign(payload, JWT_SECRET, { expiresIn: 24 * 60 * 60 });
  const refreshToken = jwtSign(payload, JWT_REFRESH_SECRET, { expiresIn: 30 * 24 * 60 * 60 });
  return { accessToken, refreshToken };
}

export function requireAuth(req: AuthRequest, res: NextApiResponse): AuthPayload | null {
  const auth = req.headers.authorization || '';
  let token = auth.startsWith('Bearer ') ? auth.slice(7).trim() : '';

  if (!token && req.headers.cookie) {
    const matchAcc = req.headers.cookie.match(/access_token=([^;]+)/);
    const matchAuth = req.headers.cookie.match(/quantai_auth=([^;]+)/);
    const matchRef = req.headers.cookie.match(/refresh_token=([^;]+)/);
    token = matchAcc ? matchAcc[1] : (matchAuth ? matchAuth[1] : (matchRef ? matchRef[1] : ''));
  }

  if (!token) {
    res.status(401).json({ error: 'Missing Bearer token' });
    return null;
  }

  if (isMasterToken(token)) {
    const payload = createAdminPayload();
    req.user = payload;
    return payload;
  }

  const payload = verifyToken(token) || verifyRefreshToken(token);
  if (!payload) {
    res.status(401).json({ error: 'Invalid or expired token' });
    return null;
  }
  req.user = payload;
  return payload;
}

export function requireAdmin(req: AuthRequest, res: NextApiResponse): AuthPayload | null {
  const user = requireAuth(req, res);
  if (!user) return null;
  if (user.role !== 'admin') {
    res.status(403).json({ error: 'Admin role required' });
    return null;
  }
  return user;
}

export function optionalAuth(req: AuthRequest): AuthPayload | null {
  const auth = req.headers.authorization || '';
  const token = auth.startsWith('Bearer ') ? auth.slice(7).trim() : '';
  if (!token) return null;
  const payload = verifyToken(token) || verifyRefreshToken(token);
  if (payload) req.user = payload;
  return payload;
}

