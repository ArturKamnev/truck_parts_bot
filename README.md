# Telegram AI Customer-Support Bot

Production-ready MVP of a Telegram customer-support bot:

- customers chat with an OpenRouter AI assistant trained on `company_knowledge.md`;
- customers can request a human manager;
- managers work from a private in-bot panel, not from a Telegram group;
- the owner can switch the active AI model and view statistics from Telegram.

The first deployment uses long polling. Webhooks and RAG are intentionally deferred.

## Stack

- Python 3.12
- aiogram 3.x
- SQLite for local development
- PostgreSQL for Railway production
- SQLAlchemy 2 async
- Alembic
- pydantic-settings
- httpx
- pytest

## Local Environment Variables

Copy `.env.example` to `.env` and fill in:

```env
APP_ENV=development
DATABASE_URL=sqlite+aiosqlite:///./bot.db

BOT_TOKEN=
OPENROUTER_API_KEY=
OWNER_ID=
MANAGER_IDS=

DEFAULT_MODEL=deepseek/deepseek-v4-flash:free
OPENROUTER_APP_NAME=Company Support Bot
OPENROUTER_SITE_URL=

AI_HISTORY_LIMIT=12
LOG_LEVEL=INFO

INSTAGRAM_URL=
OFFICIAL_SITE_URL=
BROADCAST_RATE_PER_SECOND=20
```

Railway PostgreSQL testing can keep development manager-count rules while using Postgres:

```env
APP_ENV=development
DATABASE_URL=${{Postgres.DATABASE_URL}}
OWNER_ID=
MANAGER_IDS=
```

`OWNER_ID` and `MANAGER_IDS` must be numeric Telegram user IDs. Usernames are never used for authorization.

In `development`, `MANAGER_IDS` may contain one or more IDs, so one test manager is enough. The owner may also be included in `MANAGER_IDS` for local testing. In `production`, `MANAGER_IDS` must contain exactly 11 unique numeric IDs.

SQLite creates `bot.db` automatically when migrations run.

## Windows PowerShell Local Setup

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
alembic upgrade head
python -m app.main
```

Before `alembic upgrade head`, edit `.env` and fill `BOT_TOKEN`, `OPENROUTER_API_KEY`, `OWNER_ID`, and `MANAGER_IDS`.

## Getting Telegram IDs

Use a helper bot such as `@userinfobot` or your own trusted method to get numeric Telegram IDs:

- set your Telegram ID as `OWNER_ID`;
- set one manager ID as `MANAGER_IDS` for development, for example `MANAGER_IDS=123456789`;
- for two-account testing, use one Telegram account as customer and another as manager.

## Customer Flow

Customers use the bot in a private chat:

- `/start`;
- ask normal AI questions;
- press `👨‍💼 Связаться с менеджером`;
- continue the live manager chat in the same bot chat;
- press `🚪 Выйти из чата с менеджером` to cancel and return to AI mode.

AI answers are based on `company_knowledge.md`. If exact information is missing, the assistant should say that exact information is unavailable and suggest contacting a manager.

## Manager Flow

Managers must start the bot from their private Telegram account. They see a private menu:

- `📥 Новые обращения`;
- `💬 Мои активные чаты`;
- `📊 Моя статистика`.

To test with two Telegram accounts:

1. Start the bot as the manager account.
2. Start the bot as the customer account.
3. From the customer account, ask an AI question.
4. Press `👨‍💼 Связаться с менеджером`.
5. From the manager account, press `📥 Новые обращения`.
6. Press `✅ Взять в работу`.
7. Type a normal message as the manager. It is sent to the customer.
8. Type a normal message as the customer. It is sent to the assigned manager.
9. Press `🔒 Закрыть вопрос` from the manager ticket screen.
10. The customer returns to AI mode.

Only the assigned manager or owner can reply to a claimed ticket. Messages sent by a manager without a selected active ticket are not forwarded accidentally.

## Owner Commands

- `/admin` opens the owner panel.
- `🤖 Выбрать модель ИИ` switches between seeded OpenRouter models.
- `📊 Статистика` shows customer, AI, ticket, manager, and first-claim stats.
- `📂 Открытые обращения` lists active tickets and lets the owner open, take over, reply to, or close tickets.

## AI Models

The bot seeds exactly these OpenRouter models:

- `deepseek/deepseek-v4-flash:free`
- `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`
- `google/gemma-4-31b-it:free`

The active model is stored in `app_settings`, so owner changes persist across restarts.

## Railway Deployment

The bot uses long polling. Run exactly one Railway replica/instance for this service so two polling workers do not receive and process the same bot updates.

Railway may provide `DATABASE_URL` as `postgres://...` or `postgresql://...`. The app normalizes both forms to `postgresql+asyncpg://...` at startup and during Alembic migrations, so you can use Railway's `${{Postgres.DATABASE_URL}}` variable directly.

Production environment:

```env
APP_ENV=production
DATABASE_URL=${{Postgres.DATABASE_URL}}
OWNER_ID=
MANAGER_IDS=111,222,333,444,555,666,777,888,999,1000,1001
```

Railway settings:

- Add a PostgreSQL service.
- Set the bot service start command to `python -m app.main`.
- Set the pre-deploy migration command to `python -m alembic upgrade head`.
- Keep the root `Dockerfile`; it uses Python 3.12 and installs runtime dependencies from `pyproject.toml`.
- Use a restart policy suitable for a continuously running worker. Do not enable serverless assumptions or sleep-only behavior.
- Keep replicas at `1`.

Manual Railway variables to fill:

- `BOT_TOKEN`
- `OPENROUTER_API_KEY`
- `APP_ENV`
- `DATABASE_URL`
- `OWNER_ID`
- `MANAGER_IDS`
- `DEFAULT_MODEL`
- `OPENROUTER_APP_NAME`
- `OPENROUTER_SITE_URL`
- `AI_HISTORY_LIMIT`
- `LOG_LEVEL`
- `INSTAGRAM_URL`
- `OFFICIAL_SITE_URL`
- `BROADCAST_RATE_PER_SECOND`

Secrets such as bot tokens, OpenRouter keys, Telegram IDs, private URLs, and database URLs belong only in Railway variables or local `.env`. Do not commit them.

## Tests and Lint

```bash
pytest
ruff check .
```

## Deferred Features

- RAG/vector search.
- Webhooks.
- Web admin dashboard.
- Payments.
- CRM integrations.
