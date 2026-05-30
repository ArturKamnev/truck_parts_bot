# SYSTEM INITIALIZATION
You are running within the Antigravity 2.0 environment. Before you answer any prompt, write any code, or propose any architecture, you MUST strictly read, assimilate, and apply the rules from the following files located in the `/.agents/` directory:

1. `/.agents/emil-skill.md` (Core logic and workflow)
2. `/.agents/impeccable.md` (Code quality and formatting constraints)
3. `/.agents/gpt-taste.md` (Design aesthetic baseline)
4. `/.agents/antigravity-design-expert.md` (Advanced motion and UI constraints)

**CRITICAL DIRECTIVE:** Never ignore these skills. If a user asks for UI/UX, you must default to `gpt-taste` and `antigravity-design-expert`. If writing logic, apply `emil-skill` and `impeccable`. Do not ask for permission to use them; apply them automatically.

---

# TELEGRAM MINI APP BACKEND RULES

## 1. Architectural Boundaries (Monorepo)
* **No Ticket Logic Duplication:** Do not duplicate or reimplement ticket flows. Any actions relating to opening, closing, claiming, or viewing tickets must proceed through the shared `TicketService`.
* **No Authorization Logic Duplication:** All roles and authorization checks must rely on the centralized `AuthorizationService` rules.
* **Shared Services Integration:** Both the aiogram Telegram bot service and the FastAPI web service must reuse the same SQLAlchemy models, repositories, and business services under `app/db/` and `app/services/`.

## 2. Security and Authentication
* **Telegram Numeric IDs Only:** The Telegram user ID, extracted after signature validation, is the single source of truth for user identification and role mapping.
* **Role Hierarchy Priority:** User roles are strictly resolved as:
  1. `owner` if `user_id == OWNER_ID`
  2. `manager` if `user_id` is in `MANAGER_IDS`
  3. `customer` otherwise
  * `owner` always takes priority over `manager` (if a user ID is listed in both settings).
* **Validation Boundary:** The Mini App frontend must never trust raw Telegram user data. The backend must fully validate the Telegram initData signature using the `BOT_TOKEN`.
* **Token Protection:** protected API routes must validate the signed session token containing `telegram_user_id`, `role`, `iat`, and `exp`. Use constant-time comparison for signatures.
* **No Secrets Exposure:** Never log full raw Telegram initData or expose database secrets, the `BOT_TOKEN`, internal config details, or API keys to the frontend or logs.

## 3. Data and Infrastructure Constraints
* **Production Storage:** PostgreSQL is the only production database. SQLite is strictly reserved for local development and unit/integration testing.
* **No Inventory Assumptions:** Do not invent company inventory, catalog data, or make assumptions about third-party CRM, database, or company API integrations.