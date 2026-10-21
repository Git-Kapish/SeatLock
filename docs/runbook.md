# TicketRush — Operations & Runbook

Guide for operating, diagnosing, and maintaining the TicketRush platform.

---

## 1. Quickstart Commands

```bash
make up        # Build & launch full Docker Compose stack in background
make down      # Stop and remove all containers and volumes
make migrate   # Run Alembic migrations across auth, events, and booking schemas
make test      # Execute all automated test suites
make lint      # Check code formatting and linting
make fmt       # Format code and apply auto-fixes
make typecheck # Run strict mypy verification
make load-test # Run k6 flash-sale benchmark (1,000 VUs vs 100 seats)
```

---

## 2. Infrastructure Endpoints

| Component | Host / Port | Internal URL | Purpose |
| :--- | :--- | :--- | :--- |
| **Gateway** | `http://localhost:8000` | `http://gateway:8000` | Nginx perimeter reverse proxy |
| **Auth Service** | `http://localhost:8001` | `http://auth-service:8001` | Auth API |
| **Events Service** | `http://localhost:8002` | `http://events-service:8002` | Events Catalog API |
| **Booking Service** | `http://localhost:8003` | `http://booking-service:8003` | Holds & Bookings API |
| **MailHog Web UI** | `http://localhost:8025` | `http://mailhog:8025` | View confirmation emails |
| **MailHog SMTP** | `localhost:1025` | `mailhog:1025` | SMTP delivery relay |
| **LocalStack SQS** | `http://localhost:4566` | `http://localstack:4566` | Mock AWS SQS service |
| **PostgreSQL 16** | `localhost:5432` | `postgres:5432` | Database (`ticketrush`/`ticketrush`) |
| **Redis 7** | `localhost:6379` | `redis:6379` | Cache, locks, rate limits |

---

## 3. Database Migrations

Each service owns its isolated schema and maintains independent Alembic migration scripts:
```bash
# Run migrations for all services
make migrate

# Generate a new migration for booking service
uv run alembic -c services/booking/alembic.ini revision --autogenerate -m "add index"

# Revert last migration on booking service
uv run alembic -c services/booking/alembic.ini downgrade -1
```

---

## 4. Troubleshooting & Diagnostics

### Problem: Redis Connection Refused
- **Symptom**: `redis.exceptions.ConnectionError: Error connecting to redis:6379`
- **Solution**: Check if Redis container is healthy:
  ```bash
  docker compose ps redis
  docker compose logs redis
  ```

### Problem: SQS Queue Does Not Exist
- **Symptom**: `NonExistentQueue: The specified queue does not exist`
- **Solution**: The notifier worker auto-creates queues on startup. Manually recreate if needed:
  ```bash
  docker compose exec localstack awslocal sqs create-queue --queue-name ticketrush-booking-events
  docker compose exec localstack awslocal sqs create-queue --queue-name ticketrush-booking-events-dlq
  ```

### Problem: Database Schema Not Found
- **Symptom**: `UndefinedTableError: relation "booking.seats" does not exist`
- **Solution**: Verify `init-schemas.sql` ran:
  ```bash
  docker compose exec postgres psql -U ticketrush -d ticketrush -c "\dn"
  # Should show: auth, events, booking
  make migrate
  ```
