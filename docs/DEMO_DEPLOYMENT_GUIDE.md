# TelsonBase Demo Page — Deployment Guide

**Version:** 9.0.0B
**Last Updated:** March 1, 2026
**Purpose:** Step-by-step setup for the private demo page at telsonbase.online
**Audience:** Jeff Phillips — self-deploy reference

---

## What You're Building

Two things, both free:

```
telsonbase.online             ← landing page (Cloudflare Pages, static HTML)
console.telsonbase.online     ← your live TelsonBase (Cloudflare Tunnel → localhost:8000)
```

Someone visits `telsonbase.online`, sees the demo page, clicks Open Console,
lands at `console.telsonbase.online` which is your actual running TelsonBase.
The tunnel is the bridge. No open router ports. No firewall changes.

---

## Prerequisites

- TelsonBase running locally (`docker-compose up -d` → healthy)
- telsonbase.online domain in your Cloudflare account (add it if not already — free plan)
- Windows 11, PowerShell or CMD **run as Administrator**

---

## Part 1 — Install cloudflared (5 minutes)

### Step 1a — Install via winget

Open **PowerShell as Administrator** and run:

```powershell
winget install --id Cloudflare.cloudflared
```

When it finishes, verify it worked:

```powershell
cloudflared --version
```

You should see something like `cloudflared version 2024.x.x`. If you get
"command not found," close PowerShell completely and reopen as Administrator.

### Step 1b — Authenticate with your Cloudflare account

```powershell
cloudflared tunnel login
```

This opens a browser window. Log into your Cloudflare account and click
**Authorize** on the page it shows you. You'll see a success message in the
terminal. A certificate file is saved to:
`C:\Users\[YourName]\.cloudflared\cert.pem`

You won't need to touch that file — cloudflared uses it automatically.

---

## Part 2 — Create the Tunnel (3 minutes)

### Step 2a — Create a named tunnel

```powershell
cloudflared tunnel create telsonbase-demo
```

This creates a tunnel with a permanent ID. You'll see output like:

```
Created tunnel telsonbase-demo with id a1b2c3d4-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

Copy that tunnel ID — you'll need it in Step 3b.

Cloudflare saves a credentials file at:
`C:\Users\[YourName]\.cloudflared\[tunnel-id].json`

### Step 2b — Verify the tunnel exists

```powershell
cloudflared tunnel list
```

You should see `telsonbase-demo` in the list with status `inactive` (inactive
is correct — it hasn't run yet).

---

## Part 3 — Configure the Tunnel (5 minutes)

### Step 3a — Create the config file

Create a file at:
`C:\Users\[YourName]\.cloudflared\config.yml`

Paste this content (replace YOUR-TUNNEL-ID with the ID from Step 2a):

```yaml
tunnel: YOUR-TUNNEL-ID
credentials-file: C:\Users\[YourName]\.cloudflared\YOUR-TUNNEL-ID.json

ingress:
  - hostname: console.telsonbase.online
    service: http://localhost:8000
  - service: http_status:404
```

**What this does:**
- Any request to `console.telsonbase.online` gets forwarded to your local
  TelsonBase on port 8000
- Everything else returns a 404 (required catch-all rule by Cloudflare)

### Step 3b — Point the DNS at Cloudflare

```powershell
cloudflared tunnel route dns telsonbase-demo console.telsonbase.online
```

This adds a CNAME record in your Cloudflare DNS automatically. You can verify
it worked by going to: Cloudflare Dashboard → telsonbase.online → DNS →
look for a CNAME record for `console` pointing to `[tunnel-id].cfargotunnel.com`

---

## Part 4 — Run the Tunnel (2 minutes)

### Step 4a — Start the tunnel

```powershell
cloudflared tunnel run telsonbase-demo
```

You'll see log lines like:
```
INF Starting tunnel tunnelID=a1b2c3d4-...
INF Connection registered connIndex=0 location=ORD
INF Connection registered connIndex=1 location=DFW
```

Four connections registered = healthy. The tunnel is live.

**To stop it:** Ctrl+C in that terminal window.

### Step 4b — Test it

Open a browser and go to: `https://console.telsonbase.online/health`

You should see the TelsonBase health response JSON. If you do, the tunnel
is working perfectly.

---

## Part 5 — Configure TelsonBase for the Demo (3 minutes)

### Step 5a — Add CORS origins

Edit your `.env` file in `C:\Claude_Code\TelsonBase\`:

Find the line:
```
CORS_ORIGINS=...
```

Add the demo domains (keep anything already there):
```
CORS_ORIGINS=https://telsonbase.online,https://console.telsonbase.online
```

### Step 5b — Create a demo API key

Option A — Create one via the TelsonBase API (recommended):

```powershell
curl -X POST https://console.telsonbase.online/v1/auth/api-keys `
  -H "X-API-Key: YOUR_MAIN_API_KEY" `
  -H "Content-Type: application/json" `
  -d '{"name":"demo-anthropic","permissions":["read"]}'
```

Option B — Use your existing API key if this is a controlled short-term demo
(acceptable since it's a demo instance, not production).

### Step 5c — Restart TelsonBase to pick up CORS change

```powershell
docker-compose restart mcp_server
```

---

## Part 6 — Configure and Deploy the Demo Page (5 minutes)

### Step 6a — Edit the demo page config

Open: `C:\Claude_Code\TelsonBase\website-demo\index.html`

Find these two lines near the bottom of the file (inside the `<script>` tag):

```javascript
const CONSOLE_URL = 'https://console.telsonbase.online';   // your CF tunnel URL
const API_KEY     = 'YOUR_DEMO_API_KEY_HERE';              // read-only demo key
```

Replace `YOUR_DEMO_API_KEY_HERE` with the demo key from Step 5b. Leave
`CONSOLE_URL` as-is if you used `console.telsonbase.online`.

### Step 6b — Deploy to Cloudflare Pages

1. Go to: [dash.cloudflare.com](https://dash.cloudflare.com)
2. Click **Workers & Pages** in the left sidebar
3. Click **Create application** → **Pages** → **Upload assets**
4. Name it: `telsonbase-demo`
5. Drag and drop the single file: `website-demo/index.html`
6. Click **Deploy site**

Cloudflare gives you a URL like `telsonbase-demo.pages.dev` immediately.

### Step 6c — Set your custom domain

1. In the Pages project, click **Custom domains**
2. Click **Set up a custom domain**
3. Enter: `telsonbase.online`
4. Cloudflare auto-configures the DNS — click **Activate domain**

Your demo page is now live at `https://telsonbase.online`.

---

## Part 7 — Verify End-to-End (5 minutes)

Work through this checklist:

- [ ] `https://telsonbase.online` loads the demo landing page
- [ ] The status dot turns **green** within a few seconds (live instance check passes)
- [ ] Clicking "Open Live Console" opens the TelsonBase dashboard in a new tab
- [ ] API key reveal works (click blurred key → it shows)
- [ ] Paste the URL and API key into the TelsonBase connection panel → connects successfully
- [ ] Stop the tunnel (Ctrl+C) → refresh demo page → dot turns **red** → offline notice appears
- [ ] "Explore Demo Mode" button still works when offline

---

## Running the Tunnel Automatically

Right now the tunnel only runs when you have that PowerShell window open.
For the Anthropic demo period, you have two options:

**Option A — Keep the PowerShell window open**
Simplest. Just don't close it while you want the demo live.

**Option B — Run as a Windows Service (permanent)**

```powershell
# Run as Administrator
cloudflared service install
```

This installs cloudflared as a Windows service that starts automatically
with your machine and uses the config.yml you created in Step 3a.

To check it: `Services` app → look for `Cloudflare Tunnel`
To start/stop: `net start cloudflared` / `net stop cloudflared`

---

## Turning the Demo Off

When you're done with the demo period:

```powershell
# Stop the tunnel (if running as service)
net stop cloudflared

# Or just close the PowerShell window (if running manually)

# Optionally delete the tunnel entirely
cloudflared tunnel delete telsonbase-demo
```

The demo page at `telsonbase.online` can stay up — when the tunnel is off,
the page will just show the red "offline" indicator, which is fine.

---

## Quick Reference — Commands You'll Use Most

```powershell
# Start tunnel manually
cloudflared tunnel run telsonbase-demo

# Check tunnel status
cloudflared tunnel info telsonbase-demo

# List all tunnels
cloudflared tunnel list

# Check TelsonBase is reachable through tunnel
curl https://console.telsonbase.online/health

# Restart TelsonBase after .env changes
docker-compose restart mcp_server
```

---

## Troubleshooting

**"cloudflared: command not found" after install**
→ Close and reopen PowerShell as Administrator. If still not found, add
`C:\Program Files\Cloudflare\cloudflared` to your system PATH manually.

**Tunnel starts but console.telsonbase.online won't load**
→ Check that TelsonBase is actually running: `docker-compose ps`
→ Check the port: `curl http://localhost:8000/health` — should respond locally first.

**Demo page loads but status dot stays amber (checking) forever**
→ Tunnel is not running. Start it with `cloudflared tunnel run telsonbase-demo`.

**Demo page shows red (offline) but tunnel IS running**
→ CORS may be blocking the health check. Ensure `CORS_ORIGINS` in `.env`
includes `https://telsonbase.online` and you restarted mcp_server.

**"Unauthorized" error when connecting in dashboard**
→ Wrong API key. Double-check the key in `website-demo/index.html` matches
exactly what TelsonBase has registered.

---

*TelsonBase v9.0.0B — Quietfire AI — support@telsonbase.com*
