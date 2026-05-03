# LiveT BFF Gateway

Thin BFF (~200 lines target) for the LiveT Android app.

## Responsibilities (only these three)

1. **Upstream API key proxy** — LLM (DeepSeek + 豆包) / ASR (讯飞 + 阿里 + 火山) / TTS (CosyVoice) keys are held server-side only.
2. **Subscription verification** — WeChat Pay receipt / Apple IAP receipt validation.
3. **Anonymous error log forwarding** — User-toggleable Sentry forwarder.

## Hard non-goals (privacy guarantees)

- ❌ No user dialogue / PII / medical content is ever stored
- ❌ No user database (Day-1 promise — see CLAUDE.md philosophy bullet #3)
- ❌ No raw audio (only opaque chunks pass through to ASR provider, never persisted)
- ❌ No analytics on conversation content

## Stack

- Python 3.8+ (3.11+ recommended; current Linux dev box has 3.8)
- FastAPI 0.104+ (last LTS supporting 3.8)
- uvicorn (ASGI server)
- slowapi (Redis-backed rate limit)
- httpx (upstream HTTP)
- Pydantic v2

## Layout

```
gateway/
├── main.py                  # FastAPI entry (~50 lines)
├── api/
│   ├── llm_proxy.py         # LLM dual-provider routing
│   ├── asr_proxy.py         # ASR multi-provider routing
│   ├── tts_proxy.py         # TTS proxy
│   ├── subscription.py      # WeChat Pay / Apple IAP verify
│   └── error_log.py         # Sentry forwarder
├── core/
│   ├── rate_limit.py        # Redis + slowapi limits
│   ├── auth.py              # Device ID + short-lived token
│   ├── routing.py           # Provider health check + route picker
│   └── settings.py          # Env config (via pydantic-settings)
├── pyproject.toml
├── requirements.txt
├── Caddyfile                # Reverse proxy + auto-HTTPS
└── .env.example
```

## Local dev

```bash
# 1. Create venv (Python 3.8 OK, 3.11 better)
python3 -m venv .venv && source .venv/bin/activate

# 2. Install
pip install -r requirements.txt

# 3. Copy env template and fill
cp .env.example .env
# (edit .env: add upstream API keys)

# 4. Run
uvicorn main:app --reload --port 8000

# 5. Sanity
curl http://localhost:8000/healthz
```

## Production deploy (target: Aliyun lightweight server, ¥99/month)

```bash
# (Single VM, systemd-managed, Caddy reverse proxy + auto HTTPS)
sudo systemctl enable livet-gateway
sudo systemctl start livet-gateway
sudo caddy run --config /etc/caddy/Caddyfile
```

See `docs/11-engineering-plan.md §1.9` for full deploy plan.

## Cost target

- Aliyun lightweight 2C2G : ¥99/month
- Domain : ¥80/year
- Sentry free tier : ¥0
- Redis: same VM (no separate Redis cloud)

## Privacy CI

CI grep enforces no audio file persistence in this repo. See `scripts/privacy-grep-check.sh`.
