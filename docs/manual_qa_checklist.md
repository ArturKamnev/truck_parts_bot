# Beta Release Manual QA Checklist

Follow this checklist to verify application flows and security boundaries before launching the beta release.

---

## 1. Bot Menus & Web App Launch Button Stability

- [ ] **Launch Button Presence:** In a private chat with the support bot, verify that the keyboard contains `💬 Открыть Mini App` if `MINIAPP_URL` is set.
- [ ] **Launch Button Absence (Empty URL):** Temporarily clear `MINIAPP_URL` in config, restart the bot, and verify that the `💬 Открыть Mini App` button disappears, while the rest of the customer buttons remain in place.
- [ ] **Launch Button Absence (Temporary States):** Request a manager as a customer. Verify that the keyboard switches to `❌ Отменить запрос` or similar cancel buttons, and that the `💬 Открыть Mini App` button is hidden.
- [ ] **Private Chat Constraint:** Add the bot to a Telegram group chat. Verify that the customer keyboard is never sent or exposed there, keeping keyboards private.

---

## 2. Secure Authentication & Session Tokens

- [ ] **Production Auth via Telegram Client:** Open the Mini App inside the Telegram Mobile app. Confirm that the page loads, authenticates automatically, and displays your user profile.
- [ ] **Rejection of Missing initData in Production:** Attempt to open the production Mini App URL directly in a normal web browser. Verify it is rejected with a `403 Forbidden` screen reading: *"Please open this application inside the Telegram Mobile app."*
- [ ] **Development Mock Authentication Panel:** Run the app locally in development mode (`APP_ENV=development`). Open the local browser (e.g. `http://localhost:5173`). Confirm that the mock auth panel is visible and allows choosing between Customer, Manager, and Owner roles.
- [ ] **Production Mock Rejection:** Ensure that even if the development frontend code is built, the production backend (`APP_ENV=production`) immediately rejects mock hashes with a `401 Unauthorized` response.
- [ ] **Stale Session Screen (401):** Verify that if your token is expired or tampered with, the app transitions to the "Session Expired" card with a reload action button.
- [ ] **Network Offline Screen (0):** Disconnect your internet connection or stop the backend API. Reload the Mini App and verify it shows the "Connection Offline" warning card with a retry button.

---

## 3. Customer Role Operations

- [ ] **Empty State:** Log in as a customer with no tickets. Verify that the dashboard displays the empty state: *"No support requests found."*
- [ ] **Requests List:** Send a request to a manager from the Telegram bot. Reload the Mini App customer dashboard and confirm the ticket is visible.
- [ ] **Interactive Chat Feed:** Open the ticket and verify that you can send messages if active.
- [ ] **Broadcast Settings Toggle:** Go to the Profile tab. Toggle the "Получать рассылки" switch off. Confirm that `/api/me` reflects the change, and check the database to verify `broadcasts_enabled` is set to False.
- [ ] **Telegram Bot Fallback Button:** Go to the Profile tab. Click the "Перейти в Telegram-бот" button. Confirm that it opens the main Telegram chat with the bot.

---

## 4. Manager Role Operations

- [ ] **New Tickets Queue:** Log in as a manager. Open the "New Tickets" tab. Confirm that unclaimed tickets appear in the list.
- [ ] **Ticket Claiming:** Click **Claim Ticket** (or **Взять в работу**). Verify that the ticket state updates to `CLAIMED` and the customer receives a Telegram bot notification: *"К вашему обращению подключился менеджер..."*
- [ ] **Interactive Composer:** Open the claimed ticket. Verify that the input composer is active.
- [ ] **Manager Messaging:** Type a message and press **Send**. Confirm that:
  - The message optimistically renders in the feed.
  - The message status updates to "sent" on success.
  - The customer receives the message inside their Telegram bot chat.
- [ ] **Customer Relaying:** Send a reply as a customer from Telegram. Verify that the message appears in the manager's Mini App chat feed.
- [ ] **Cross-Manager Isolation:** Log in as a second manager. Try to access the first manager's claimed ticket. Verify that the endpoint returns `403 Forbidden`.
- [ ] **Ticket Closure:** Click **Close** in the header. Confirm closure, and verify:
  - The ticket status updates to `CLOSED`.
  - The composer is replaced with *"Ticket is closed. Composer disabled."*
  - The customer receives a Telegram notification that the ticket is resolved.
- [ ] **Closed Tickets Sub-Tab:** Confirm that closed tickets claimed/resolved by the manager are listed under the "Closed Chats" sub-tab.
- [ ] **Personal Statistics:** Go to the Profile tab. Confirm that stats cards show the correct number of claimed and closed tickets for this manager.

---

## 5. Owner Role Operations

- [ ] **Supervisor Safety Toggle:** Log in as the owner. Open any ticket. Verify that by default:
  - The composer is disabled with: *"You are in read-only mode. Enable Supervisor Mode above to write."*
  - The close button is hidden.
- [ ] **Supervisor Activation:** Check the **Act as Supervisor** toggle. Verify that the composer input and close actions are unlocked.
- [ ] **Supervisor Messaging:** Send a message with Supervisor mode enabled. Confirm the customer receives it.
- [ ] **Supervisor Takeover:** Close a ticket claimed by a manager. Verify that the status updates to `CLOSED` and notifications are delivered.
- [ ] **AI Model Settings:** Go to the "More" tab (ProfileView). Locate the "Настройки AI модели" section. Verify:
  - The currently active model is checked.
  - Clicking another model starts a switch request and shows a loading state.
  - Switching to an allowed model succeeds and updates settings immediately.
  - Swapping to a disallowed model (by manual request manipulation) fails with 400 Bad Request.
- [ ] **Broadcast History Logs:** Go to the "More" tab. Locate the "История рассылок" section. Verify:
  - It lists recent broadcasts with IDs and statuses.
  - It shows correct delivery statistics (recipients, delivered, failed, blocked counts).
  - No private user messages or error stack traces are exposed.
  - There is a clear instruction card with a shortcut pointing to the bot for creating new broadcasts.
- [ ] **Dashboard Shortcuts:** Test the "Менеджеры" and "Статистика" shortcuts in the Profile tab. Confirm they instantly switch the bottom navigation view to the correct tabs.

---

## 6. Composer & Connection Reliability

- [ ] **Closed Composer Block:** Open any closed or cancelled ticket. Verify that the composer is disabled and displays a clean banner warning that the ticket is closed.
- [ ] **Click Spam Throttling:** Enter a message and spam the send button (or double-click/hit Enter multiple times). Verify that the message is sent exactly once (no duplicate messages in DB or UI).
- [ ] **Network Interruptions:** Simulate a network drop during a message send. Verify that the message is marked as "FAILED" with a retry action, and no duplicate message is created on retry.
- [ ] **Dynamic Role Sync:** Promoted a customer to a manager using the owner dashboard. Switch to the customer's Mini App page and change tab. Confirm that their layout immediately refreshes to the manager navigation menu without cache clears.

