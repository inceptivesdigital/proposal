# Deploying to Vercel

Fifteen minutes end to end.

---

## What it costs

| Piece | Cost |
|---|---|
| Vercel | free on Hobby; $20/month Pro for longer function timeouts |
| Neon Postgres | **free**: 0.5 GB and 100 compute-hours a month, permanent, commercial use allowed |
| Screenshots (ScreenshotOne) | roughly $10 to $20 a month at normal volume |
| Claude | roughly **$0.20 to $0.50 per proposal** on Opus |

The Admin panel measures your real per-proposal number once you have generated
a few.

**Storage grows slowly.** A proposal with its full version history is about
50 KB and a learned rule is one row, so two thousand proposals fit inside the
free tier. That is what makes keeping the learning worthwhile.

One exception: UI screens are large. Keep them out of the database if you
generate a lot, see "Screens and storage" below.

---

## 1. Create the database

1. Vercel → your project → **Storage** → **Create Database** → **Neon
   Postgres**. Or sign up at neon.tech and create a project.
2. Copy the connection string, which looks like
   `postgresql://user:password@ep-xxx.neon.tech/neondb?sslmode=require`

Vercel's integration sets `DATABASE_URL` for you. From neon.tech you add it by
hand in step 3.

The schema builds itself on first run. Nothing to import.

---

## 2. Email for sign-up codes

Nobody can create an account without a code emailed to them, so this has to
work before anyone can sign in.

With Google Workspace, which you already have:

1. myaccount.google.com/apppasswords → create one for
   `proposals@inceptivesdigital.com`
2. Note the 16-character password

Postmark, Resend and SendGrid also work and deliver better at volume.

---

## 3. Environment variables

Vercel → Settings → Environment Variables. Tick **Production, Preview and
Development** on each.

**Required**

    DATABASE_URL           the Neon connection string
    ANTHROPIC_API_KEY      from console.anthropic.com
    PROPOSAL_MODEL         claude-opus-5
    ENVIRONMENT            production
    COOKIE_SECURE          1
    ALLOWED_EMAIL_DOMAINS  inceptivesdigital.com
    SMTP_HOST              smtp.gmail.com
    SMTP_PORT              587
    SMTP_USER              proposals@inceptivesdigital.com
    SMTP_PASSWORD          the app password
    SMTP_FROM              proposals@inceptivesdigital.com
    OTP_DEV_ECHO           0

**For UI screens**

    SCREENSHOT_PROVIDER    screenshotone
    SCREENSHOT_API_KEY     your ACCESS key, not the secret key

**Optional**

    UNSPLASH_ACCESS_KEY    free from unsplash.com/developers. With it, photos
                           inside the generated screens match their subject;
                           without it, real photographs are still used but are
                           chosen by seed rather than by subject.
    V0_API_KEY             only for the slow, high-quality route
    SESSION_DAYS           14
    LOGIN_MAX_ATTEMPTS     8
    OTP_MINUTES            10

`OTP_DEV_ECHO=0` matters. Left at 1, codes print to the log instead of being
emailed, which is right on a laptop and wrong in production.

---

## 4. Deploy

**Dependencies live in `pyproject.toml`.** Vercel installs from that file when
it exists and ignores `requirements.txt`, so anything added to one must be added
to the other. `/api/health` lists which packages actually loaded.

When redeploying after a dependency change, **turn off the build cache**, or the
install step is skipped and the package never arrives.

Push to GitHub, or from the folder:

    vercel --prod

---

## 5. Create the administrator

**The first account to finish sign-up becomes the administrator.** Do this
yourself straight after deploying, before sharing the URL.

1. Open your Vercel URL
2. **Create an account instead**
3. Your name, your @inceptivesdigital.com email, a password of 10+ characters
4. **Enter the six-digit code from your email**
5. You are in as administrator, and an **Admin** button appears in the header

Everyone after joins as a member. Promote or disable them from Admin → People.

If administrator access is ever lost, run against the database:

    UPDATE users SET role = 'admin' WHERE email = 'you@inceptivesdigital.com';

---

## Forgotten passwords

On the sign-in screen: enter the email address, click **Forgotten your
password?**, and a six-digit code is emailed. The code plus a new password of
10 characters or more completes it.

Resetting **ends every existing session for that account**, so if someone's
password was the reason for the reset, anyone holding it is signed out.

The reply is identical whether or not the address has an account, so the form
cannot be used to find out who works here.

## 6. Check it

Open `/api/health`:

    "database": "postgres"
    "mail_configured": true
    "warnings": []

An empty `warnings` list means nothing is left in a development setting.
Anything listed says exactly what and why.

Then **API health** in the header calls Claude and the screenshot service for
real and reports whether each key works and has credit.

---

## Screens and storage

UI screens are held with the proposal, roughly 200 KB each. At seven per
proposal that is 1.4 MB, so about 350 proposals fills the free 0.5 GB.

Text alone would take thousands of proposals to get there. If you generate
screens on most proposals, move them to object storage (Vercel Blob or S3) and
keep only the URL in the database. Until then, watch the storage figure in the
Neon dashboard.

---

## What the Admin panel shows

- **System health** — build, artwork, keys, models, database backend, whether
  email is configured, which domains may register
- **Spend** — total, average per proposal, calls, tokens
- **Spend by user** and **by proposal**, so any client's proposal can be priced
- **Where the money goes**, split by writing, screenshots and v0
- **Activity by user**, and a full trail of who did what and when
- **People** — promote to administrator, or disable an account, which ends
  their sessions immediately
- **Billable calls**, one row per call with its cost
- **What the system has learned** — every standing rule and where it came from

---

## Security

- Sign-up limited to your domain, and refused without an emailed code
- Codes expire in 10 minutes, allow 5 attempts, and are rate limited
- PBKDF2-SHA256 at 240,000 iterations with a per-user salt; a password is
  hashed even for unknown accounts, so timing reveals nothing
- One identical failure message for wrong password, unknown account and
  disabled account
- Lockout after repeated failures on an address
- Sessions expire and are checked on every request; disabling a user ends
  their sessions at once
- HttpOnly, SameSite cookies, Secure when `COOKIE_SECURE=1`
- Content security policy, DENY framing, no MIME sniffing, no referrer, and
  camera, microphone and location switched off
- Assets served by basename with an extension allow-list
- Admin checks on the server, never in the browser

Worth adding at the edge: a rate limit in Vercel or Cloudflare, on top of the
per-account one here.

---

## Running it locally

    cd proposal-creator
    ./start.sh

With no `DATABASE_URL` it uses a local SQLite file; with no mail server the
sign-up code prints in the terminal. Both are deliberate so you can work
offline, and both appear as warnings in `/api/health`.

To test against Neon before deploying, put `DATABASE_URL` in `keys.env`.
