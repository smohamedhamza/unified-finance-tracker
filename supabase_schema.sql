-- Supabase PostgreSQL Schema for Unified Finance App
-- Copy this entire file and run it inside the Supabase SQL Editor.

-- 1. Friends / Users
CREATE TABLE IF NOT EXISTS friends (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

-- 2. Categories
CREATE TABLE IF NOT EXISTS categories (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    icon TEXT,
    type TEXT NOT NULL -- 'income' or 'expense'
);

-- 3. Accounts
CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    initial_balance NUMERIC DEFAULT 0.0,
    icon TEXT
);

-- 4. Splitwise Expenses
CREATE TABLE IF NOT EXISTS expenses (
    id TEXT PRIMARY KEY,
    description TEXT,
    amount NUMERIC NOT NULL,
    payer_id TEXT REFERENCES friends(id) ON DELETE CASCADE,
    payer_account_id TEXT REFERENCES accounts(id) ON DELETE SET NULL,
    participants JSONB NOT NULL, -- Dictionary of user IDs to amounts
    date TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. Personal Transactions
CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL, -- 'income' or 'expense'
    amount NUMERIC NOT NULL,
    category_id TEXT REFERENCES categories(id) ON DELETE SET NULL,
    account_id TEXT REFERENCES accounts(id) ON DELETE CASCADE,
    description TEXT,
    date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    linked_split_id TEXT -- Corresponds to expenses.id or payments.id
);

-- 6. Settlement Payments
CREATE TABLE IF NOT EXISTS payments (
    id TEXT PRIMARY KEY,
    "from" TEXT REFERENCES friends(id) ON DELETE CASCADE,
    "to" TEXT REFERENCES friends(id) ON DELETE CASCADE,
    amount NUMERIC NOT NULL,
    status TEXT DEFAULT 'pending', -- 'pending' or 'accepted'
    date TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 7. Recursive Schemes
CREATE TABLE IF NOT EXISTS recurring (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL, -- 'income' or 'expense'
    amount NUMERIC NOT NULL,
    category_id TEXT REFERENCES categories(id) ON DELETE SET NULL,
    account_id TEXT REFERENCES accounts(id) ON DELETE CASCADE,
    description TEXT,
    frequency TEXT NOT NULL, -- 'Daily', 'Weekly', 'Monthly'
    next_date TIMESTAMP WITH TIME ZONE NOT NULL,
    active BOOLEAN DEFAULT TRUE
);
