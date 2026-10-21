"""Seeds database with 1,000 test users, 1 active flash-sale event, and 100 available seats."""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg

from ticketrush_common.security import create_access_token

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://ticketrush:ticketrush@localhost:5432/ticketrush",
)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
JWT_SECRET = os.getenv(
    "JWT_SECRET_KEY",
    "development-insecure-secret-key-change-in-production-min-32-chars",
)
PAYMENT_WEBHOOK_SECRET = os.getenv(
    "PAYMENT_WEBHOOK_SECRET",
    "development-payment-webhook-secret-key-min-32-chars",
)


async def seed() -> None:
    """Connects to Postgres and populates flash sale test dataset."""
    print("Connecting to database...")
    # Convert asyncpg compatible URL
    pg_url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(pg_url)

    try:
        print("Cleaning previous test data...")
        await conn.execute("DELETE FROM booking.booking_seats")
        await conn.execute("DELETE FROM booking.bookings")
        await conn.execute("DELETE FROM booking.hold_seats")
        await conn.execute("DELETE FROM booking.holds")
        await conn.execute("DELETE FROM booking.payments")
        await conn.execute("DELETE FROM booking.seats")
        await conn.execute("DELETE FROM events.events WHERE slug = 'flash-sale-load-test'")
        await conn.execute("DELETE FROM auth.users WHERE email LIKE 'loadtest_%'")

        # 1. Create 1,000 pre-authenticated users & JWT tokens
        print("Generating 1,000 test users and JWT access tokens...")
        user_records: list[dict[str, str]] = []
        user_rows: list[tuple[Any, ...]] = []
        now = datetime.now(UTC)

        for i in range(1, 1001):
            user_id = uuid.uuid4()
            email = f"loadtest_user_{i}@ticketrush.internal"
            token = create_access_token(
                user_id=str(user_id),
                email=email,
                role="customer",
                secret_key=JWT_SECRET,
                expires_delta=timedelta(hours=24),
            )
            user_records.append(
                {
                    "user_id": str(user_id),
                    "email": email,
                    "token": token,
                }
            )
            user_rows.append(
                (
                    user_id,
                    email,
                    "$argon2id$v=19$m=65536,t=3,p=4$dummyhashforseedpurposesonly",
                    "customer",
                    now,
                    now,
                )
            )

        await conn.executemany(
            """
            INSERT INTO auth.users (id, email, password_hash, role, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            user_rows,
        )

        # 2. Create 1 Event in status 'on_sale'
        event_id = uuid.uuid4()
        event_slug = "flash-sale-load-test"
        starts_at = now + timedelta(days=7)
        ends_at = starts_at + timedelta(hours=3)

        print(f"Creating test event: {event_id}...")
        await conn.execute(
            """
            INSERT INTO events.events (
                id, title, slug, description, venue_name, venue_city,
                starts_at, ends_at, status, total_capacity, created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            """,
            event_id,
            "Flash Sale: Championship Arena",
            event_slug,
            "High concurrency load testing event with 100 seats and 1,000 users",
            "Metropolis Stadium",
            "Metropolis",
            starts_at,
            ends_at,
            "on_sale",
            100,
            now,
            now,
        )

        # 3. Create exactly 100 seats (5 rows of 20 seats)
        print("Generating 100 seats across 5 rows...")
        seat_ids: list[str] = []
        seat_rows: list[tuple[Any, ...]] = []
        row_letters = ["A", "B", "C", "D", "E"]

        for row in row_letters:
            for num in range(1, 21):
                seat_id = uuid.uuid4()
                seat_ids.append(str(seat_id))
                seat_rows.append(
                    (
                        seat_id,
                        event_id,
                        "General Admission",
                        "Section-1",
                        row,
                        num,
                        "available",
                        1,
                        now,
                        now,
                    )
                )

        await conn.executemany(
            """
            INSERT INTO booking.seats (
                id, event_id, tier, section, row, seat_number,
                status, version, created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
            seat_rows,
        )

        # 4. Save test_data.json for k6 runner
        data_path = os.path.join(os.path.dirname(__file__), "test_data.json")
        test_data = {
            "event_id": str(event_id),
            "seat_ids": seat_ids,
            "users": user_records,
            "webhook_secret": PAYMENT_WEBHOOK_SECRET,
        }

        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(test_data, f, indent=2)

        print(f"Seed complete! Generated data saved to {data_path}")
        print(f"Summary: 1,000 users, 1 event ({event_id}), 100 available seats.")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed())
