# SLK Admin Panel + Email Access

This add-on keeps the scanner on GitHub Actions and adds a free cloud access-control layer.

## Architecture

- **Supabase**: users + pending access requests + admin authentication.
- **Cloudflare Worker**: receives Telegram `/start <token>` webhooks and links Telegram to email.
- **Cloudflare Pages / GitHub Pages**: hosts `web/index.html` (landing page) and `web/admin.html` (admin panel).
- **GitHub Actions**: continues running the scanner and broadcasts alerts to users whose status is `active`.

## 1. Create Supabase project

Create a project, open SQL Editor, replace `YOUR_ADMIN_EMAIL@example.com` in `supabase/schema.sql` with your admin email, and run it.

In Authentication, create the admin user with that same email and a strong password.

Copy the project URL and the **anon** key for the web pages. Copy the **service role** key only into private server/Actions secrets. Never put the service-role key in `web/*.html`.

## 2. Configure landing/admin pages

In both `web/index.html` and `web/admin.html`, replace:

- `YOUR_SUPABASE_URL`
- `YOUR_SUPABASE_ANON_KEY`
- `YOUR_BOT_USERNAME` (landing page only, without `@`)

Host the `web` folder as a static site. You can use Cloudflare Pages or another static host.

## 3. Telegram webhook

Create a Cloudflare Worker from `worker/worker.js`. Add Worker secrets/variables:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `TELEGRAM_BOT_TOKEN`

After deployment, set the Telegram webhook to:

`https://YOUR-WORKER-DOMAIN/telegram`

Use Telegram's Bot API `setWebhook` endpoint once. Do not commit your bot token.

## 4. GitHub Actions secrets

Add these repository secrets:

- `TELEGRAM_BOT_TOKEN`
- `TWELVEDATA_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

`TELEGRAM_CHAT_ID` is optional legacy fallback. With the new access system, alerts go to active users from Supabase.

## 5. User flow

1. User enters their email on the landing page.
2. A one-time token is stored as a pending access request.
3. User is sent to Telegram with `/start <token>`.
4. Worker links Telegram ID to that email and marks the user `pending`.
5. Admin logs into the panel and clicks **Approve**.
6. Scanner broadcasts only to users with `status=active`.
7. **Revoke** immediately removes that user from future broadcasts.

## Important

- Do not commit Supabase service-role keys or Telegram bot tokens.
- This system controls access to the bot; it does not change the SLK signal logic.
- The scanner still sends storyline/bias information only; it does not add entries, SL, TP, or lot sizing.
