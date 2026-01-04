# Cloudflare Tunnel Setup Guide

This guide shows you how to expose your Menu AI app to the internet using Cloudflare Tunnel, so others can access it via a public URL.

## What is Cloudflare Tunnel?

Cloudflare Tunnel creates a secure connection between your local app and the internet without requiring port forwarding or a static IP. It's:
- **Free** - No cost for basic usage
- **Secure** - Encrypted tunnel to Cloudflare's network
- **Easy** - No account required for quick tunnels
- **Fast** - Global CDN for low latency

## Prerequisites

- Your Menu AI app running locally (via Docker Compose or manually)
- Cloudflare Tunnel installed (cloudflared)

## Installation

### Install cloudflared

```bash
# macOS
brew install cloudflared

# Linux
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared.deb

# Windows
# Download from: https://github.com/cloudflare/cloudflared/releases
```

### Verify Installation

```bash
cloudflared --version
# Should output: cloudflared version 2025.11.1 (or similar)
```

## Quick Start (No Account Required)

### Expose Frontend Only

This is the simplest option - expose just the frontend. External users can view the UI but won't be able to use features that require the backend.

```bash
# Make sure your app is running
docker compose up -d

# Start the tunnel
cloudflared tunnel --url http://localhost:3000
```

You'll see output like:
```
+--------------------------------------------------------------------------------------------+
|  Your quick Tunnel has been created! Visit it at (it may take some time to be reachable):  |
|  https://your-unique-url.trycloudflare.com                                                 |
+--------------------------------------------------------------------------------------------+
```

**Share this URL** with anyone you want to access your app!

### Expose Frontend + Backend (Full Functionality)

For external users to have full functionality (menu parsing, restaurant search), you need to expose both services.

#### Terminal 1 - Frontend Tunnel

```bash
cloudflared tunnel --url http://localhost:3000
```

Note the URL (e.g., `https://frontend-abc123.trycloudflare.com`)

#### Terminal 2 - Backend Tunnel

```bash
cloudflared tunnel --url http://localhost:8000
```

Note the URL (e.g., `https://backend-xyz789.trycloudflare.com`)

#### Terminal 3 - Update Frontend to Use Public Backend

You need to update the frontend to use the public backend URL:

```bash
# Open docker-compose.yml and add environment variable for frontend:
nano docker-compose.yml
```

Add this under `frontend` service:
```yaml
frontend:
  environment:
    - NEXT_PUBLIC_API_URL=https://backend-xyz789.trycloudflare.com
```

Then restart the frontend:
```bash
docker compose restart frontend
```

Now external users can use all features!

## Run Tunnel in Background

By default, the tunnel runs in the foreground. To run it in the background:

```bash
# Background mode (frontend)
nohup cloudflared tunnel --url http://localhost:3000 > /tmp/frontend-tunnel.log 2>&1 &

# Background mode (backend)
nohup cloudflared tunnel --url http://localhost:8000 > /tmp/backend-tunnel.log 2>&1 &

# View the URLs in the logs
cat /tmp/frontend-tunnel.log | grep "trycloudflare.com"
cat /tmp/backend-tunnel.log | grep "trycloudflare.com"
```

## Stop/Turn Off Tunnel

### Stop Foreground Tunnel

If running in the foreground (you see the tunnel output), simply press:
```
Ctrl + C
```

### Stop Background Tunnel

If running in the background:

```bash
# Find the process
ps aux | grep cloudflared

# Kill all cloudflared processes
pkill cloudflared

# Or kill specific process by PID
kill <PID>
```

### Verify Tunnel is Stopped

```bash
# Check if cloudflared is still running
ps aux | grep cloudflared

# Should show nothing (except the grep command itself)
```

## Advanced: Named Tunnels (Production)

For production use or permanent URLs, create a named tunnel:

### 1. Sign Up for Cloudflare

- Go to: https://dash.cloudflare.com/sign-up
- Create a free account

### 2. Authenticate

```bash
cloudflared tunnel login
```

This opens a browser where you select your domain.

### 3. Create a Named Tunnel

```bash
# Create tunnel
cloudflared tunnel create menu-ai-app

# You'll get a Tunnel ID - save this!
```

### 4. Configure the Tunnel

Create `~/.cloudflared/config.yml`:

```yaml
url: http://localhost:3000
tunnel: <YOUR_TUNNEL_ID>
credentials-file: /Users/yourusername/.cloudflared/<YOUR_TUNNEL_ID>.json
```

### 5. Route Traffic

```bash
# Route subdomain to tunnel
cloudflared tunnel route dns menu-ai-app menu.yourdomain.com
```

### 6. Run Named Tunnel

```bash
# Foreground
cloudflared tunnel run menu-ai-app

# Background (persistent)
cloudflared tunnel run menu-ai-app &

# Or install as system service
sudo cloudflared service install
sudo cloudflared service start
```

### Stop Named Tunnel Service

```bash
# Stop service
sudo cloudflared service stop

# Uninstall service
sudo cloudflared service uninstall
```

## Troubleshooting

### Tunnel shows URL but app doesn't load

1. **Check your app is running**:
   ```bash
   docker compose ps
   # All services should show "Up"
   ```

2. **Test locally first**:
   ```bash
   curl http://localhost:3000
   # Should return HTML
   ```

3. **Wait a moment** - Tunnels can take 30-60 seconds to become fully active

### "Connection refused" error

- Make sure your Docker containers are running: `docker compose up -d`
- Verify the port numbers match (3000 for frontend, 8000 for backend)
- Check Docker logs: `docker compose logs frontend`

### Backend API calls fail for external users

- You need to expose the backend tunnel as well (see "Expose Frontend + Backend" above)
- Or update frontend environment to use the public backend URL

### Multiple tunnels running

```bash
# List all processes
ps aux | grep cloudflared

# Kill all
pkill cloudflared
```

## Security Considerations

### Quick Tunnels (account-less)
- **No uptime guarantee** - Tunnel can be terminated anytime
- **Temporary URLs** - URL changes each time you restart
- **Not for production** - Use named tunnels instead

### Best Practices
- Don't expose sensitive data through quick tunnels
- Use authentication in your app if needed
- Monitor tunnel logs regularly
- For production, use named tunnels with proper DNS

## Useful Commands

```bash
# Check if cloudflared is running
ps aux | grep cloudflared

# View all tunnels (named tunnels only)
cloudflared tunnel list

# View tunnel info
cloudflared tunnel info menu-ai-app

# Test connection
curl https://your-tunnel-url.trycloudflare.com

# View logs (background tunnels)
cat /tmp/frontend-tunnel.log
cat /tmp/backend-tunnel.log
```

## Alternative: ngrok

If you prefer ngrok instead:

```bash
# Install
brew install ngrok

# Sign up and get auth token from: https://dashboard.ngrok.com/get-started/your-authtoken

# Configure
ngrok config add-authtoken YOUR_TOKEN_HERE

# Expose frontend
ngrok http 3000

# Expose backend (new terminal)
ngrok http 8000
```

## Summary

**Quick Start (Frontend Only):**
```bash
cloudflared tunnel --url http://localhost:3000
```

**Stop Tunnel:**
```bash
pkill cloudflared
```

**Full Setup (Frontend + Backend):**
```bash
# Terminal 1
cloudflared tunnel --url http://localhost:3000

# Terminal 2
cloudflared tunnel --url http://localhost:8000

# Terminal 3 - Update frontend config and restart
```

That's it! Your Menu AI app is now accessible to anyone on the internet. 🎉

## Need Help?

- Cloudflare Tunnel Docs: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/
- Menu AI App Issues: See README.md
- Cloudflare Support: https://community.cloudflare.com/
