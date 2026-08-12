/**
 * auth.ts - Lightweight JWT implementation (no external deps).
 * HS256 only. Suitable for in-house internal tokens.
 * Uses Node's built-in crypto module.
 */
import type { NextApiRequest, NextApiResponse } from 'next';
import crypto from 'crypto';

const JWT_SECRET = process.env.JWT_SECRET || 'ate-quanttrading-jwt-secret-2026-do-not-use-in-prod';
const JWT_REFRESH_SECRET = process.env.JWT_REFRESH_SECRET || 'ate-refresh-jwt-secret-2026-do-not-use-in-prod';

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
  const now = Math.floor(Date.now() / 1000);
  const full = { ...payload, iat: now, exp: now + opts.expiresIn };
  const header = b64urlEncode(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
  const body = b64urlEncode(JSON.stringify(full));
  const sig = hmacSign(secret, `${header}.${body}`);
  return `${header}.${body}.${sig}`;
}

function jwtVerify<T>(token: string, secret: string): T | null {
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

export function verifyToken(token: string): AuthPayload | null {
  return jwtVerify<AuthPayload>(token, JWT_SECRET);
}

export function verifyRefreshToken(token: string): AuthPayload | null {
  return jwtVerify<AuthPayload>(token, JWT_REFRESH_SECRET);
}

export function issueTokens(payload: Omit<AuthPayload, 'iat' | 'exp'>) {
  const accessToken = jwtSign(payload, JWT_SECRET, { expiresIn: 15 * 60 });
  const refreshToken = jwtSign(payload, JWT_REFRESH_SECRET, { expiresIn: 7 * 24 * 60 * 60 });
  return { accessToken, refreshToken };
}

export function requireAuth(req: AuthRequest, res: NextApiResponse): AuthPayload | null {
  const auth = req.headers.authorization || '';
  const token = auth.startsWith('Bearer ') ? auth.slice(7) : '';
  if (!token) {
    res.status(401).json({ error: 'Missing Bearer token' });
    return null;
  }
  const payload = verifyToken(token);
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
  const token = auth.startsWith('Bearer ') ? auth.slice(7) : '';
  if (!token) return null;
  const payload = verifyToken(token);
  if (payload) req.user = payload;
  return payload;
}
