#!/usr/bin/env python3
"""Seed a dev tenant, admin user, and sample agent for local development."""

import json
import os
import sys

import psycopg

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://private_ai:private_ai@localhost:5432/private_ai"
)


def seed():
    with psycopg.connect(DATABASE_URL) as conn:
        # Check if already seeded
        row = conn.execute("SELECT id FROM tenants WHERE slug = 'dev'").fetchone()
        if row:
            print(f"Dev tenant already exists (id={row[0]}). Skipping seed.")
            return

        # Create tenant
        tenant = conn.execute(
            "INSERT INTO tenants (name, slug, theme) VALUES (%s, %s, %s::jsonb) RETURNING id",
            ("Development", "dev", json.dumps({"name": "dark"})),
        ).fetchone()
        tenant_id = tenant[0]
        print(f"Created tenant: Development (id={tenant_id})")

        # Create admin user
        user = conn.execute(
            "INSERT INTO users (tenant_id, email, role) VALUES (%s, %s, %s) RETURNING id, email",
            (str(tenant_id), "dev@localhost", "admin"),
        ).fetchone()
        print(f"Created admin user: {user[1]} (id={user[0]})")

        # Create a sample agent
        agent = conn.execute(
            "INSERT INTO agents (tenant_id, name, slug, description, prompt_md, mode) "
            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id, name",
            (str(tenant_id), "General Assistant", "general-assistant",
             "A helpful general-purpose assistant",
             "You are a helpful assistant. Answer questions clearly and concisely. "
             "If you don't know something, say so.",
             "interactive"),
        ).fetchone()
        print(f"Created agent: {agent[1]} (id={agent[0]})")

        # Create demo tools
        echo_tool = conn.execute(
            "INSERT INTO tools (tenant_id, name, description, endpoint, method, auth_type, "
            "input_schema, timeout_ms) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s) "
            "ON CONFLICT (tenant_id, name) DO NOTHING RETURNING id, name",
            (str(tenant_id), "echo", "Echoes back the input — useful for testing",
             "https://httpbin.org/post", "POST", "none",
             json.dumps({"type": "object", "properties": {"message": {"type": "string"}}}),
             5000),
        ).fetchone()
        if echo_tool:
            print(f"Created tool: {echo_tool[1]} (id={echo_tool[0]})")

        weather_tool = conn.execute(
            "INSERT INTO tools (tenant_id, name, description, endpoint, method, auth_type, "
            "input_schema, timeout_ms) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s) "
            "ON CONFLICT (tenant_id, name) DO NOTHING RETURNING id, name",
            (str(tenant_id), "weather", "Get current weather for a city (plain text)",
             "https://wttr.in", "GET", "none",
             json.dumps({"type": "object", "properties": {"city": {"type": "string"}}}),
             5000),
        ).fetchone()
        if weather_tool:
            print(f"Created tool: {weather_tool[1]} (id={weather_tool[0]})")

        conn.commit()
        print("\nSeed complete. Log in at http://localhost:5001 as dev@localhost")


if __name__ == "__main__":
    seed()
