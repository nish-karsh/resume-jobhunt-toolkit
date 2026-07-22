# NVIDIA NIM Models

This toolkit runs entirely on **free** models hosted by NVIDIA NIM through an OpenAI-compatible API. This doc explains the model choices, the free-tier limits, and how to change or inspect models.

---

## The endpoint

- **Base URL:** `https://integrate.api.nvidia.com/v1` (OpenAI-compatible)
- **Auth:** an `nvapi-` key in `.env` as `NVIDIA_API_KEY`
- **Get a key:** sign in at [build.nvidia.com](https://build.nvidia.com), open any model, click **Get API Key**

Because it is OpenAI-compatible, the app uses the standard `openai` Python SDK pointed at NVIDIA's base URL.

---

## The model chain (from `config/settings.yaml`)

| Role | Model | Why this one |
|------|-------|--------------|
| **Tailoring (`models.tailor`)** | `meta/llama-3.3-70b-instruct` | Dedicated default for resume tailoring: a reliable instruct model that returns clean, complete JSON. The reasoning-heavy primary tended to emit long `<think>` output and truncate the tailored resume (the "only the summary generated" bug), so tailoring uses this by default. Falls back through the chain below. |
| **Primary** | `nvidia/nemotron-3-super-120b-a12b` | Free-endpoint flagship with ~1M context and strong reasoning; default for non-tailoring calls (research, etc.). |
| **Fallback 1** | `nvidia/llama-3.3-nemotron-super-49b-v1.5` | High accuracy, faster, 128K context. Used when the primary is busy. |
| **Fallback 2** | `meta/llama-3.3-70b-instruct` | Rock-solid, broadly available - the safety net. |
| **Utility** | `nvidia/nemotron-3-nano-30b-a3b` | Small/fast/cheap - used for keyword extraction and light structured tasks. |
| **High-end alt** | `qwen/qwen3.5-397b-a17b` | Optional heavier alternative you can promote to primary. |
| **Offline** | local TF-IDF (scikit-learn) | No network; picks the closest cached variant. Not a NIM model. |

The tailoring call also strips `<think>...</think>` blocks, extracts JSON robustly (balanced-brace scan), and does one "return only clean JSON" repair retry if a response is truncated.

**How the chain behaves:** `NimClient` tries the primary; on a 429 (rate limit), 503 (worker/capacity limit), or timeout, it retries with exponential backoff and then moves to the next model in the chain. This is why an occasional 503 on the 120B model is harmless - the app quietly continues on a fallback.

> These slugs were verified live against the catalog. NVIDIA rotates its catalog frequently, so if a slug ever stops working, pick a current one (see "Inspect available models" below) and update `settings.yaml`.

---

## Free-tier limits

- **~40 requests per minute.** This toolkit makes only ~4 calls for a full job cycle (ingest keyword extraction, tailor, cover letter, email), so normal use is comfortably within limits. Rebuilding the 6 offline variants uses ~6 calls.
- No credit card required; intended for evaluation/prototyping - perfect for a personal job hunt.
- If you batch-process many jobs quickly you may hit 429s; the client backs off and retries automatically. Space out large batches.

---

## Inspect available models

```powershell
venv\Scripts\activate
python -m src.nim_client          # prints reachability + the live model list
python -m src.nim_client --smoke  # makes one tiny chat call to confirm your key works
```

You can also query the catalog directly:

```powershell
curl -H "Authorization: Bearer %NVIDIA_API_KEY%" https://integrate.api.nvidia.com/v1/models
```

---

## Change the model

**Permanently:** edit `config/settings.yaml` and restart the app. For example, to prioritize the Qwen alternative:

```yaml
models:
  primary: qwen/qwen3.5-397b-a17b
  fallbacks:
    - nvidia/nemotron-3-super-120b-a12b
    - meta/llama-3.3-70b-instruct
```

**For one session only:** use an environment override (no file edit):

```powershell
$env:SETTINGS__MODELS__PRIMARY = "nvidia/llama-3.3-nemotron-super-49b-v1.5"
streamlit run app.py
```

### Choosing a model

- **Tailoring (default):** keep `models.tailor: meta/llama-3.3-70b-instruct` for reliable, complete output. To experiment with the reasoning model, set `SETTINGS__MODELS__TAILOR=nvidia/nemotron-3-super-120b-a12b` (watch for truncation on long resumes).
- **Non-tailoring quality:** keep `nemotron-3-super-120b-a12b` as `primary`.
- **Faster / fewer rate-limit hits:** set `nvidia/llama-3.3-nemotron-super-49b-v1.5` as primary.
- Keep at least one broadly-available model (like `meta/llama-3.3-70b-instruct`) in the fallback list for reliability.

---

## Privacy note

Only the text you send when you click Tailor / ATS / Cover letter / Email is transmitted - to NVIDIA's API, over HTTPS. Your resume, tracker, and `.env` otherwise stay on your PC. See the privacy section of the root [README.md](../README.md) and [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for related notes.
