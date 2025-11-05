# GitHub App Webhook Server for PR Security Analysis

This HTTP server receives GitHub webhook events and automatically performs security analysis on pull requests using the NullKrypt3rs security analyzer.

## Features

- 🔐 **Secure Webhook Handling**: Validates GitHub webhook signatures
- 🤖 **Automated PR Analysis**: Triggers security scans on PR events (opened, synchronized, reopened)
- 💬 **Inline Comments**: Posts analysis results directly to PRs
- 🔍 **Comprehensive Security Checks**: Line-by-line analysis with security-focused LLM agents
- ⚡ **Async Processing**: Non-blocking analysis using background threads
- 📊 **Health Monitoring**: Built-in health check endpoints

## Quick Start

### 1. Install Dependencies

```bash
cd /home/hiteshrawat/nullkrypt3rs
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy the example environment file and fill in your credentials:

```bash
cd httpapi
cp .env.example .env
```

Edit `.env` with your configuration:

```bash
# Required
GITHUB_TOKEN=ghp_your_github_token
GITHUB_WEBHOOK_SECRET=your_secret_here
OPENAI_API_KEY=sk-your_openai_key  # or ANTHROPIC_API_KEY

# Optional (defaults shown)
LLM_MODEL=o3-mini
LLM_PROVIDER=openai
HOST=0.0.0.0
PORT=8080
```

### 3. Run the Server

```bash
# From the httpapi directory
python server.py

# Or from the project root
python -m httpapi.server

# Or use the start script
chmod +x start_server.sh
./start_server.sh
```

### 4. Configure GitHub Webhook

1. Go to your GitHub repository → Settings → Webhooks → Add webhook
2. Set the Payload URL: `http://your-server:8080/webhook`
3. Set Content type: `application/json`
4. Set Secret: Use the same value as `GITHUB_WEBHOOK_SECRET`
5. Select events: Choose "Pull requests" or "Let me select individual events"
6. Make sure "Active" is checked
7. Click "Add webhook"

## API Endpoints

### `POST /webhook`
Receives GitHub webhook events for pull requests.

**Supported Events:**
- `pull_request.opened` - New PR created
- `pull_request.synchronize` - New commits pushed to PR
- `pull_request.reopened` - PR reopened
- `ping` - Webhook test event

**Response:**
```json
{
  "status": "success",
  "message": "Analysis started for PR #123",
  "pr_url": "https://github.com/owner/repo/pull/123"
}
```

### `GET /health`
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-11-05T12:00:00",
  "config": {
    "webhook_secret_configured": true,
    "github_token_configured": true,
    "llm_model": "o3-mini",
    "llm_provider": "openai"
  }
}
```

### `GET /`
Server information and status.

## GitHub Token Permissions

Your GitHub Personal Access Token needs the following scopes:

- `repo` - Full control of private repositories
- `write:discussion` - Post PR comments

To create a token:
1. Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token
3. Select the required scopes
4. Copy the token and add it to your `.env` file

## How It Works

1. **Webhook Received**: GitHub sends a webhook when a PR is opened/updated
2. **Signature Validation**: Server validates the webhook signature for security
3. **Initial Comment**: Posts "Analysis in progress" comment to the PR
4. **Analysis**: Runs security analysis using LLM-powered agents:
   - Line-by-line code review
   - Security vulnerability detection
   - Code quality assessment
5. **Results Posted**: Formats and posts comprehensive security report as PR comment
6. **Results Saved**: Saves detailed JSON results to `results/` directory

## Analysis Workflow

```
GitHub PR Event
      ↓
Webhook Received & Validated
      ↓
Post "Analysis in Progress" Comment
      ↓
Fetch PR Data & Diff
      ↓
Line-by-Line Analysis (LLM Agent 1)
      ↓
Security Analysis (LLM Agent 2)
      ↓
Format Report & Post Comment
      ↓
Save Results to JSON
```

## Security Considerations

- **Webhook Secret**: Always set `GITHUB_WEBHOOK_SECRET` to validate webhooks
- **Token Security**: Keep your `GITHUB_TOKEN` and API keys secure
- **HTTPS**: Use HTTPS in production (consider using nginx as reverse proxy)
- **Firewall**: Restrict access to GitHub's webhook IPs if possible

## Deployment

### Local Development

```bash
python server.py
```

### Production with Gunicorn

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8080 httpapi.server:app
```

### Docker Deployment

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8080
CMD ["python", "httpapi/server.py"]
```

### systemd Service

Create `/etc/systemd/system/nullkrypt3rs-webhook.service`:

```ini
[Unit]
Description=NullKrypt3rs Webhook Server
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/home/hiteshrawat/nullkrypt3rs
Environment="PATH=/home/hiteshrawat/nullkrypt3rs/venv/bin"
EnvironmentFile=/home/hiteshrawat/nullkrypt3rs/httpapi/.env
ExecStart=/home/hiteshrawat/nullkrypt3rs/venv/bin/python httpapi/server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable nullkrypt3rs-webhook
sudo systemctl start nullkrypt3rs-webhook
sudo systemctl status nullkrypt3rs-webhook
```

### ngrok for Testing

If you want to test webhooks locally:

```bash
ngrok http 8080
```

Use the ngrok URL as your webhook URL in GitHub.

## Troubleshooting

### Webhook Not Triggering

1. Check GitHub webhook delivery logs (Settings → Webhooks → Recent Deliveries)
2. Verify server is accessible from internet
3. Check server logs: `tail -f ../server.log`

### Signature Validation Fails

- Ensure `GITHUB_WEBHOOK_SECRET` matches the secret in GitHub webhook settings
- Check that the secret doesn't have extra whitespace

### Comments Not Posted

- Verify `GITHUB_TOKEN` has correct permissions
- Check token hasn't expired
- Ensure repository access is granted

### Analysis Errors

- Check LLM API keys are valid
- Verify LLM provider is accessible
- Check server logs for detailed error messages

## Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `GITHUB_TOKEN` | - | GitHub Personal Access Token (required) |
| `GITHUB_WEBHOOK_SECRET` | - | Webhook secret for signature validation |
| `LLM_MODEL` | `o3-mini` | LLM model to use for analysis |
| `LLM_PROVIDER` | `openai` | LLM provider (`openai`, `claude`, etc.) |
| `OPENAI_API_KEY` | - | OpenAI API key (if using OpenAI) |
| `ANTHROPIC_API_KEY` | - | Anthropic API key (if using Claude) |
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8080` | Server port |

## Monitoring

### Logs

Logs are written to:
- Console (stdout/stderr)
- `../server.log` (if logger is configured)

### Metrics

Check server status:
```bash
curl http://localhost:8080/health
```

## Contributing

Contributions are welcome! Please ensure:
- Code follows existing style
- Error handling is comprehensive
- Logging is informative
- Security best practices are followed

## License

See LICENSE file in the repository root.

## Support

For issues or questions:
1. Check server logs
2. Review GitHub webhook delivery logs
3. Open an issue on GitHub

