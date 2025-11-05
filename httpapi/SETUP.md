# GitHub Webhook Server Setup Guide

Complete setup instructions for the NullKrypt3rs GitHub webhook server.

## Prerequisites

- Python 3.8 or higher
- GitHub account with admin access to a repository
- API key for your chosen LLM provider (OpenAI, Anthropic, etc.)
- Server accessible from the internet (for GitHub webhooks)

## Step 1: Install Dependencies

```bash
cd /home/hiteshrawat/nullkrypt3rs

# Activate virtual environment if you have one
source venv/bin/activate  # or .venv/bin/activate

# Install required packages
pip install -r requirements.txt
```

## Step 2: Create Environment Configuration

Create a `.env` file in the `httpapi` directory:

```bash
cd httpapi
cat > .env << 'EOF'
# GitHub Configuration
GITHUB_TOKEN=your_github_token_here
GITHUB_WEBHOOK_SECRET=your_secret_here

# LLM Configuration
LLM_MODEL=o3-mini
LLM_PROVIDER=openai

# OpenAI API Key (if using OpenAI)
OPENAI_API_KEY=your_openai_key_here

# Server Configuration
HOST=0.0.0.0
PORT=8080
EOF
```

### Getting Your GitHub Token

1. Go to https://github.com/settings/tokens
2. Click "Generate new token" → "Generate new token (classic)"
3. Give it a descriptive name: "NullKrypt3rs Webhook"
4. Select scopes:
   - ✅ `repo` - Full control of private repositories
   - ✅ `write:discussion` - Write access to discussions
5. Click "Generate token"
6. Copy the token (starts with `ghp_`)
7. Add it to your `.env` file

### Creating a Webhook Secret

Generate a secure random secret:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Copy the output and add it to your `.env` file.

### Getting Your LLM API Key

**For OpenAI:**
1. Go to https://platform.openai.com/api-keys
2. Click "Create new secret key"
3. Copy the key (starts with `sk-`)
4. Add to `.env` as `OPENAI_API_KEY`

**For Anthropic (Claude):**
1. Go to https://console.anthropic.com/
2. Navigate to API Keys
3. Create a new key
4. Add to `.env` as `ANTHROPIC_API_KEY`

## Step 3: Test the Server Locally

```bash
# From the project root
cd /home/hiteshrawat/nullkrypt3rs

# Load environment variables
export $(cat httpapi/.env | grep -v '^#' | xargs)

# Start the server
python httpapi/server.py
```

You should see output like:
```
============================================================
NullKrypt3rs GitHub Webhook Server
============================================================
LLM Model: o3-mini
LLM Provider: openai
Webhook Secret: Configured
GitHub Token: Configured
Host: 0.0.0.0
Port: 8080
============================================================
Starting server on 0.0.0.0:8080...
```

Test the health endpoint:
```bash
curl http://localhost:8080/health
```

## Step 4: Make Server Accessible from Internet

For GitHub to send webhooks, your server must be publicly accessible. Options:

### Option A: ngrok (for testing)

```bash
# Install ngrok
# Download from https://ngrok.com/download

# Start ngrok tunnel
ngrok http 8080
```

You'll get a public URL like `https://abc123.ngrok.io`. Use this for your webhook URL.

### Option B: Deploy to Cloud

**Deploy to Railway:**
```bash
# Install Railway CLI
npm i -g @railway/cli

# Login and deploy
railway login
railway init
railway up
```

**Deploy to Render:**
1. Push code to GitHub
2. Go to https://render.com
3. Create new Web Service
4. Connect your GitHub repo
5. Set environment variables
6. Deploy

### Option C: Use Your Own Server

If you have a VPS or server with a public IP:

1. Ensure port 8080 is open in firewall
2. Consider using nginx as reverse proxy for HTTPS
3. Use systemd to run as a service (see README.md)

## Step 5: Configure GitHub Webhook

1. Go to your repository on GitHub
2. Navigate to **Settings** → **Webhooks** → **Add webhook**

3. Configure the webhook:
   ```
   Payload URL: http://your-server-ip:8080/webhook
              (or https://your-domain.com/webhook)
   
   Content type: application/json
   
   Secret: [paste your GITHUB_WEBHOOK_SECRET]
   
   Which events: Select "Let me select individual events"
                 ✅ Pull requests
                 (uncheck everything else)
   
   Active: ✅ (checked)
   ```

4. Click **Add webhook**

## Step 6: Test the Webhook

### Test with the test script:

```bash
cd /home/hiteshrawat/nullkrypt3rs

# Set webhook URL (your server URL)
export WEBHOOK_URL="http://localhost:8080/webhook"
export GITHUB_WEBHOOK_SECRET="your_secret_here"

# Run tests
python httpapi/test_webhook.py
```

### Test with a real PR:

1. Create a test pull request in your repository
2. Watch the webhook deliveries in GitHub:
   - Settings → Webhooks → Click on your webhook
   - Check "Recent Deliveries"
3. You should see:
   - A successful delivery (green checkmark)
   - Response code 202
4. Check your PR for comments from the bot

## Step 7: Verify Everything Works

1. **Check webhook delivery in GitHub:**
   - Go to Settings → Webhooks
   - Click on your webhook
   - Look at "Recent Deliveries"
   - Should see successful deliveries with 200/202 status

2. **Check server logs:**
   ```bash
   # If running in terminal, you'll see logs directly
   # Or check log file if configured
   tail -f ../server.log
   ```

3. **Check PR comments:**
   - Open the PR you created
   - You should see:
     - "Analysis in Progress" comment
     - Followed by detailed security analysis report

4. **Check saved results:**
   ```bash
   ls -la results/
   # Should see JSON files with analysis results
   ```

## Troubleshooting

### Webhook shows 401 Unauthorized
- Check that `GITHUB_WEBHOOK_SECRET` in your `.env` matches the secret in GitHub webhook settings
- Verify no extra whitespace in the secret

### Webhook shows 500 Error
- Check server logs for detailed error
- Verify all environment variables are set correctly
- Ensure LLM API key is valid

### No comments on PR
- Verify `GITHUB_TOKEN` has correct permissions
- Check that token hasn't expired
- Ensure repository access is granted to the token

### Analysis fails
- Check LLM API key is valid and has credits
- Verify PR URL is accessible with your GitHub token
- Check server logs for specific error messages

### Server won't start
- Verify port 8080 isn't already in use
- Check all dependencies are installed
- Ensure virtual environment is activated

## Production Deployment Tips

### Use Environment Variables

Don't commit `.env` file. Use your platform's environment variable settings:

- **Railway**: Settings → Variables
- **Render**: Environment → Environment Variables
- **Heroku**: Settings → Config Vars
- **Docker**: Use docker-compose.yml or -e flags

### Enable HTTPS

Use nginx or your platform's HTTPS:

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Monitor Your Server

Set up monitoring for:
- Server uptime
- Webhook delivery success rate
- Analysis completion rate
- API usage/costs

### Set Resource Limits

For Docker:
```yaml
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 2G
```

For systemd, use `MemoryLimit=` and `CPUQuota=` in service file.

### Implement Rate Limiting

Add rate limiting to prevent abuse:

```python
from flask_limiter import Limiter

limiter = Limiter(app, default_limits=["100 per hour"])
```

## Security Best Practices

1. ✅ Always use `GITHUB_WEBHOOK_SECRET` in production
2. ✅ Use HTTPS for webhook URL
3. ✅ Keep API keys secure (never commit to git)
4. ✅ Rotate tokens regularly
5. ✅ Monitor webhook logs for suspicious activity
6. ✅ Use principle of least privilege for GitHub token
7. ✅ Keep dependencies updated
8. ✅ Implement rate limiting
9. ✅ Use environment variables for all secrets
10. ✅ Enable firewall rules to restrict access

## Next Steps

Once everything is working:

1. **Customize analysis**: Modify prompts in `pr_analyzer.py`
2. **Add filters**: Skip analysis for certain file types or authors
3. **Integration**: Connect to Slack, Discord, or other tools
4. **Metrics**: Add monitoring and analytics
5. **Scale**: Use job queues (Celery, RQ) for large repos

## Getting Help

- Check the [README.md](README.md) for detailed documentation
- Review [server.py](server.py) code and comments
- Check GitHub webhook delivery logs
- Review server logs for errors
- Open an issue on GitHub

## Quick Reference

### Start Server
```bash
cd /home/hiteshrawat/nullkrypt3rs
source venv/bin/activate
export $(cat httpapi/.env | grep -v '^#' | xargs)
python httpapi/server.py
```

### Test Webhook
```bash
curl http://localhost:8080/health
python httpapi/test_webhook.py
```

### View Logs
```bash
tail -f server.log
```

### Check Results
```bash
ls -la results/
cat results/pr_*.json | jq .
```

