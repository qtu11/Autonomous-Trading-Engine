-- PostgreSQL Initialization Script for GoldQuant AI
-- Creates schema for trading system with proper indexing and constraints

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create schema
CREATE SCHEMA IF NOT EXISTS quantai;

-- ============================================================
-- USERS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS quantai.users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    avatar_url TEXT,
    ip_address VARCHAR(45),
    role VARCHAR(20) DEFAULT 'user' CHECK (role IN ('user', 'admin')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_users_email ON quantai.users(email);
CREATE INDEX IF NOT EXISTS idx_users_deleted_at ON quantai.users(deleted_at) WHERE deleted_at IS NULL;

-- ============================================================
-- PRODUCTS TABLE (Source Code Listings)
-- ============================================================
CREATE TABLE IF NOT EXISTS quantai.products (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES quantai.users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    price DECIMAL(10,2) NOT NULL CHECK (price >= 0),
    file_url TEXT NOT NULL,
    thumbnail TEXT NOT NULL,
    tags JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_products_user_id ON quantai.products(user_id);
CREATE INDEX IF NOT EXISTS idx_products_deleted_at ON quantai.products(deleted_at) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_products_tags ON quantai.products USING GIN(tags);

-- ============================================================
-- TRANSACTIONS TABLE (Financial Transactions)
-- ============================================================
CREATE TABLE IF NOT EXISTS quantai.transactions (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES quantai.users(id) ON DELETE CASCADE,
    type VARCHAR(20) NOT NULL CHECK (type IN ('deposit', 'withdraw', 'purchase')),
    amount DECIMAL(10,2) NOT NULL CHECK (amount > 0),
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    method VARCHAR(50) NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON quantai.transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_transactions_status ON quantai.transactions(status);
CREATE INDEX IF NOT EXISTS idx_transactions_type ON quantai.transactions(type);
CREATE INDEX IF NOT EXISTS idx_transactions_created_at ON quantai.transactions(created_at DESC);

-- ============================================================
-- REVIEWS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS quantai.reviews (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES quantai.users(id) ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES quantai.products(id) ON DELETE CASCADE,
    rating INT NOT NULL CHECK (rating >= 1 AND rating <= 5),
    comment TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    UNIQUE(user_id, product_id)
);

CREATE INDEX IF NOT EXISTS idx_reviews_product_id ON quantai.reviews(product_id);
CREATE INDEX IF NOT EXISTS idx_reviews_user_id ON quantai.reviews(user_id);

-- ============================================================
-- CHATS TABLE (Support Messages)
-- ============================================================
CREATE TABLE IF NOT EXISTS quantai.chats (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES quantai.users(id) ON DELETE CASCADE,
    admin_id UUID REFERENCES quantai.users(id),
    message TEXT NOT NULL,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_chats_user_id ON quantai.chats(user_id);
CREATE INDEX IF NOT EXISTS idx_chats_created_at ON quantai.chats(created_at DESC);

-- ============================================================
-- NOTIFICATIONS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS quantai.notifications (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES quantai.users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    type VARCHAR(20) NOT NULL CHECK (type IN ('system', 'deposit', 'withdraw', 'chat')),
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON quantai.notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_is_read ON quantai.notifications(is_read) WHERE is_read = FALSE;
CREATE INDEX IF NOT EXISTS idx_notifications_created_at ON quantai.notifications(created_at DESC);

-- ============================================================
-- TRADING SPECIFIC TABLES
-- ============================================================

-- Trading Signals from AI
CREATE TABLE IF NOT EXISTS quantai.trading_signals (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    signal VARCHAR(10) NOT NULL CHECK (signal IN ('BUY', 'SELL', 'WAIT', 'CLOSE')),
    confidence DECIMAL(5,2),
    entry_price DECIMAL(10,2),
    stop_loss DECIMAL(10,2),
    take_profit DECIMAL(10,2),
    suggested_lot DECIMAL(8,2),
    reasoning TEXT,
    indicators JSONB,
    market_data JSONB,
    executed BOOLEAN DEFAULT FALSE,
    executed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_signals_symbol ON quantai.trading_signals(symbol);
CREATE INDEX IF NOT EXISTS idx_signals_executed ON quantai.trading_signals(executed);
CREATE INDEX IF NOT EXISTS idx_signals_created_at ON quantai.trading_signals(created_at DESC);

-- Executed Trades
CREATE TABLE IF NOT EXISTS quantai.executed_trades (
    id BIGSERIAL PRIMARY KEY,
    signal_id BIGINT REFERENCES quantai.trading_signals(id),
    ticket BIGINT UNIQUE NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    type VARCHAR(10) NOT NULL CHECK (type IN ('BUY', 'SELL')),
    volume DECIMAL(8,2) NOT NULL,
    price_open DECIMAL(10,2) NOT NULL,
    price_close DECIMAL(10,2),
    sl DECIMAL(10,2),
    tp DECIMAL(10,2),
    profit DECIMAL(10,2) DEFAULT 0,
    swap DECIMAL(10,2) DEFAULT 0,
    commission DECIMAL(10,2) DEFAULT 0,
    magic INT DEFAULT 888999,
    comment TEXT,
    opened_at TIMESTAMPTZ NOT NULL,
    closed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trades_ticket ON quantai.executed_trades(ticket);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON quantai.executed_trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_opened_at ON quantai.executed_trades(opened_at DESC);
CREATE INDEX IF NOT EXISTS idx_trades_closed_at ON quantai.executed_trades(closed_at DESC) WHERE closed_at IS NOT NULL;

-- Account Snapshots (for equity curve)
CREATE TABLE IF NOT EXISTS quantai.account_snapshots (
    id BIGSERIAL PRIMARY KEY,
    login BIGINT NOT NULL,
    server VARCHAR(100) NOT NULL,
    balance DECIMAL(15,2) NOT NULL,
    equity DECIMAL(15,2) NOT NULL,
    margin DECIMAL(15,2) NOT NULL,
    free_margin DECIMAL(15,2) NOT NULL,
    margin_level DECIMAL(10,2),
    floating_pnl DECIMAL(15,2) GENERATED ALWAYS AS (equity - balance) STORED,
    recorded_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_snapshots_login_time ON quantai.account_snapshots(login, recorded_at DESC);

-- Market Data Cache
CREATE TABLE IF NOT EXISTS quantai.market_data (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    bid DECIMAL(10,2) NOT NULL,
    ask DECIMAL(10,2) NOT NULL,
    spread DECIMAL(10,2) GENERATED ALWAYS AS (ask - bid) STORED,
    volume BIGINT,
    timestamp TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_market_symbol_time ON quantai.market_data(symbol, timestamp DESC);

-- AI Analysis Cache
CREATE TABLE IF NOT EXISTS quantai.ai_analysis (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    analysis_type VARCHAR(50) NOT NULL,
    result JSONB NOT NULL,
    confidence DECIMAL(5,2),
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analysis_symbol_type ON quantai.ai_analysis(symbol, analysis_type);
CREATE INDEX IF NOT EXISTS idx_analysis_expires ON quantai.ai_analysis(expires_at) WHERE expires_at > NOW();

-- ============================================================
-- TRIGGERS FOR UPDATED_AT
-- ============================================================
CREATE OR REPLACE FUNCTION quantai.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE
    tbl record;
BEGIN
    FOR tbl IN SELECT table_name FROM information_schema.tables WHERE table_schema = 'quantai' AND table_type = 'BASE TABLE'
    LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS update_%I_updated_at ON quantai.%I', tbl.table_name, tbl.table_name);
        EXECUTE format('CREATE TRIGGER update_%I_updated_at BEFORE UPDATE ON quantai.%I FOR EACH ROW EXECUTE FUNCTION quantai.update_updated_at_column()', tbl.table_name, tbl.table_name);
    END LOOP;
END $$;

-- ============================================================
-- DEFAULT ADMIN USER (password: changeme - change on first login!)
-- ============================================================
INSERT INTO quantai.users (id, name, email, password_hash, role)
VALUES (
    uuid_generate_v4(),
    'Nguyễn Quang Tú',
    'admin@goldquant.local',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj/RK.PZvO.S', -- bcrypt hash of 'changeme'
    'admin'
) ON CONFLICT (email) DO NOTHING;

-- ============================================================
-- GRANT PERMISSIONS
-- ============================================================
GRANT USAGE ON SCHEMA quantai TO quantai;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA quantai TO quantai;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA quantai TO quantai;
ALTER DEFAULT PRIVILEGES IN SCHEMA quantai GRANT ALL ON TABLES TO quantai;
ALTER DEFAULT PRIVILEGES IN SCHEMA quantai GRANT ALL ON SEQUENCES TO quantai;

-- ============================================================
-- COMPLETION MESSAGE
-- ============================================================
DO $$
BEGIN
    RAISE NOTICE 'GoldQuant AI Database Schema initialized successfully!';
    RAISE NOTICE 'Schema: quantai';
    RAISE NOTICE 'Default admin: admin@goldquant.local / changeme';
END $$;