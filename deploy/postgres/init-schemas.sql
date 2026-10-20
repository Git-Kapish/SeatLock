-- Initialize separate schemas for service data isolation
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS events;
CREATE SCHEMA IF NOT EXISTS booking;

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
