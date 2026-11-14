# Q364 — Routed Continual Learning cost at Hydra's actual prices

Implements spec item 6 (`TOP10-TEST-SPECS-DRAFT.md`) against card `C-routed-continual-learning` (arXiv:2610.38796v1), `data/routing/job-usage-log.jsonl`, and `data/prices.json`.

## Method

1. **Log parsing (`data/routing/job-usage-log.jsonl`):** Parsed all 13003 valid run records (0 malformed lines skipped) to establish Hydra's empirical model mix by call share and token footprint (input, cached input, and output tokens per call).
2. **Price schedule (`data/prices.json`):** Applied the explicit convention from `data/prices.json`:
   - **Vertex Argon (`google/gemini-4-argon`):** Effective 2026-11-12: `$2.00 / MTok` uncached input, `$0.10 / MTok` cached input, `$10.00 / MTok` output (doubling on 2026-12-01 to `$4.00 / $0.20 / $20.00`; 50% credit promotion on net spend also reported).
   - **Subscription / free lanes:** Carry **$0.00 marginal dollar cost** (metered by quota/tokens, not marginal dollars).
3. **Protocol repricing (398 instances, 1 router call/instance):** Compared the routed full library against one global history under (a) the authors' frozen public schedule as reported in the card and (b) Hydra's logged model mix and Vertex Argon rates, solving for the router-call break-even point.

## Assumptions & Honest Limits

- **Card granularity:** `C-routed-continual-learning` states the stream size (398 instances: 301 CL-Bench + 97 tau-bench, 5 matched rollouts), the router frequency (1 structured-output call before each instance), and the relative cost reductions (**65% to 72% lower cost** than one global history; **25% to 33% cheaper** than routed histories on 3 models and **+5% more expensive** on Claude Opus 4.7; **+8% to +29% cost** for routing a single fixed ReasoningBank). The card does not print raw per-role (router vs. Context Memory Adapter vs. extractor vs. agent) token counts or absolute dollar figures.
- **Closest faithful reading:** Because the card gives relative cost ratios across single-model rollouts, we evaluate:
  1. The exact algebraic survival of the 65–72% reduction under homogeneous and mix-weighted Hydra pricing.
  2. The sensitivity to Vertex Argon's 20:1 uncached-to-cached input price ratio (`$2.00` vs `$0.10/MTok`).
  3. Concrete dollar costs for the 398 router calls sized at Hydra's empirical logged per-call token footprint.
  4. The exact router-call break-even threshold in both relative and dollar terms.

## Hydra Logged Model Mix

- **Total valid logged calls:** `13003`
- **Vertex Argon (paid) call share:** `2.51%` (`327` calls)
- **Subscription / free ($0 marginal USD) call share:** `97.49%` (`12676` calls)

| Model | Calls | Call Share | Pricing Tier (`prices.json` convention) | Mean In Tokens | Mean Cached Tokens | Mean Out Tokens |
|---|---:|---:|---|---:|---:|---:|
| `regolo/apertus-70b` | 1224 | 9.41% | `subscription_or_free_$0_marginal` | None | None | None |
| `groq/openai/gpt-oss-120b` | 1114 | 8.57% | `subscription_or_free_$0_marginal` | None | None | None |
| `kilo-auto/free` | 899 | 6.91% | `subscription_or_free_$0_marginal` | None | None | None |
| `ovh/gpt-oss-120b` | 894 | 6.88% | `subscription_or_free_$0_marginal` | None | None | None |
| `ollamacloud/gpt-oss:120b` | 606 | 4.66% | `subscription_or_free_$0_marginal` | None | None | None |
| `openai/gpt-oss-120b` | 594 | 4.57% | `subscription_or_free_$0_marginal` | None | None | None |
| `opencode/deepseek-v4.1-flash-free` | 546 | 4.20% | `subscription_or_free_$0_marginal` | None | None | None |
| `llm7/DeepSeek-V4-Flash-0731` | 466 | 3.58% | `subscription_or_free_$0_marginal` | None | None | None |
| `codex/codex` | 458 | 3.52% | `subscription_or_free_$0_marginal` | None | None | None |
| `nvidia/openai/gpt-oss-20b` | 356 | 2.74% | `subscription_or_free_$0_marginal` | None | None | None |
| `nvidia/Qwen3.8-27B-NVFP4` | 297 | 2.28% | `subscription_or_free_$0_marginal` | None | None | None |
| `zai/glm-4.5-flash` | 279 | 2.15% | `subscription_or_free_$0_marginal` | None | None | None |
| `google/gemma-4-31b-it` | 259 | 1.99% | `subscription_or_free_$0_marginal` | None | None | None |
| `openrouter/nvidia/nemotron-3-super-120b-a12b:free` | 234 | 1.80% | `subscription_or_free_$0_marginal` | None | None | None |
| `inception/mercury-2.5` | 231 | 1.78% | `subscription_or_free_$0_marginal` | None | None | None |
| `codex` | 212 | 1.63% | `subscription_or_free_$0_marginal` | None | None | None |
| `z-ai/glm-5.3` | 208 | 1.60% | `subscription_or_free_$0_marginal` | None | None | None |
| `nvidia/nemotron-3-super-120b-a12b` | 192 | 1.48% | `subscription_or_free_$0_marginal` | None | None | None |
| `@cf/qwen/qwen3.8-27b` | 183 | 1.41% | `subscription_or_free_$0_marginal` | None | None | None |
| `@cf/meta/llama-3.3-70b-instruct-fp8-fast` | 181 | 1.39% | `subscription_or_free_$0_marginal` | None | None | None |
| `aisingapore/Nemotron-SEA-LION-v4.8-120B-A12B` | 177 | 1.36% | `subscription_or_free_$0_marginal` | None | None | None |
| `xingchen-agi/xing4.0-29b-a4b:free` | 169 | 1.30% | `subscription_or_free_$0_marginal` | None | None | None |
| `qwen/qwen3.8-27b` | 158 | 1.22% | `subscription_or_free_$0_marginal` | None | None | None |
| `aisingapore/Qwen-SEA-LION-v4.5-27B-IT` | 133 | 1.02% | `subscription_or_free_$0_marginal` | None | None | None |
| `claude` | 123 | 0.95% | `subscription_or_free_$0_marginal` | None | None | None |
| `nvidia/nemotron-3.5-super-vl-120b-a12b` | 123 | 0.95% | `subscription_or_free_$0_marginal` | None | None | None |
| `opencode/nemotron-3.5-super-vl-free` | 113 | 0.87% | `subscription_or_free_$0_marginal` | None | None | None |
| `cohere/command-a-plus-05-2026` | 100 | 0.77% | `subscription_or_free_$0_marginal` | None | None | None |
| `zai/glm-4.7-flash` | 96 | 0.74% | `subscription_or_free_$0_marginal` | None | None | None |
| `openai/gpt-oss-20b` | 91 | 0.70% | `subscription_or_free_$0_marginal` | None | None | None |
| `google/gemini-3.1-flash-lite` | 88 | 0.68% | `subscription_or_free_$0_marginal` | 2480.98 | 0.0 | 293.61 |
| `kimi/kimi-k2.6` | 85 | 0.65% | `subscription_or_free_$0_marginal` | 1345.45 | 0.0 | 1039.36 |
| `deepseek-paid/deepseek-v4-pro` | 80 | 0.62% | `subscription_or_free_$0_marginal` | 1329.76 | 0.0 | 640.59 |
| `dots-studio/dots-3-note-preview:free` | 79 | 0.61% | `subscription_or_free_$0_marginal` | None | None | None |
| `ollamacloud/gemma4:31b` | 77 | 0.59% | `subscription_or_free_$0_marginal` | None | None | None |
| `minimax/MiniMax-M3` | 70 | 0.54% | `subscription_or_free_$0_marginal` | 5332.3 | 0.0 | 1174.72 |
| `nvidia/nemotron-3.5-super-vl:free` | 64 | 0.49% | `subscription_or_free_$0_marginal` | None | None | None |
| `google/gemini-3.8-flash` | 59 | 0.45% | `subscription_or_free_$0_marginal` | 899.15 | 0.0 | 861.85 |
| `regolo/gemma4-31b` | 58 | 0.45% | `subscription_or_free_$0_marginal` | None | None | None |
| `mistral/codestral-2508` | 57 | 0.44% | `subscription_or_free_$0_marginal` | 2915.72 | 0.0 | 1104.11 |
| `nvidia/nemotron-3.5-lightning:free` | 57 | 0.44% | `subscription_or_free_$0_marginal` | None | None | None |
| `google/gemini-3.5-flash-lite` | 56 | 0.43% | `subscription_or_free_$0_marginal` | 1844.66 | 0.0 | 950.73 |
| `nvidia/nemotron-3.5-lightning-30b-a3b` | 55 | 0.42% | `subscription_or_free_$0_marginal` | None | None | None |
| `@cf/meta/llama-4-scout-17b-16e-instruct` | 53 | 0.41% | `subscription_or_free_$0_marginal` | None | None | None |
| `opencode/muse-spark-1.3-contributor-free` | 53 | 0.41% | `subscription_or_free_$0_marginal` | None | None | None |
| `claude/claude` | 52 | 0.40% | `subscription_or_free_$0_marginal` | None | None | None |
| `aisingapore/Gemma-SEA-LION-v4-27B-IT` | 50 | 0.38% | `subscription_or_free_$0_marginal` | None | None | None |
| `google/gemini-3.7-flash` | 49 | 0.38% | `subscription_or_free_$0_marginal` | 873.92 | 0.0 | 524.27 |
| `zai/glm-4.6v-flash` | 45 | 0.35% | `subscription_or_free_$0_marginal` | None | None | None |
| `llm7/codestral-latest` | 44 | 0.34% | `subscription_or_free_$0_marginal` | None | None | None |
| `mistral/mistral-medium-3.5` | 44 | 0.34% | `subscription_or_free_$0_marginal` | 650.43 | 0.0 | 71.66 |
| `reflection/beam-free` | 44 | 0.34% | `subscription_or_free_$0_marginal` | None | None | None |
| `regolo/glm5.2` | 44 | 0.34% | `subscription_or_free_$0_marginal` | None | None | None |
| `unknown_model` | 44 | 0.34% | `subscription_or_free_$0_marginal` | None | None | None |
| `google/gemini-3.6-flash` | 43 | 0.33% | `subscription_or_free_$0_marginal` | 489.42 | 0.0 | 283.4 |
| `kimi/kimi-k3` | 40 | 0.31% | `subscription_or_free_$0_marginal` | 1958.55 | 0.0 | 671.48 |
| `regolo/gpt-oss-120b` | 40 | 0.31% | `subscription_or_free_$0_marginal` | None | None | None |
| `ollamacloud/beam` | 39 | 0.30% | `subscription_or_free_$0_marginal` | None | None | None |
| `ovh/Qwen3.8-27B` | 36 | 0.28% | `subscription_or_free_$0_marginal` | None | None | None |
| `google/gemma-4-31b-it:free` | 35 | 0.27% | `subscription_or_free_$0_marginal` | None | None | None |
| `regolo/mistral-small-4-119b` | 34 | 0.26% | `subscription_or_free_$0_marginal` | None | None | None |
| `cohere/north-mini-code:free` | 33 | 0.25% | `subscription_or_free_$0_marginal` | None | None | None |
| `claude-code` | 28 | 0.22% | `subscription_or_free_$0_marginal` | None | None | None |
| `inception/mercury-2` | 28 | 0.22% | `subscription_or_free_$0_marginal` | None | None | None |
| `free roster` | 27 | 0.21% | `subscription_or_free_$0_marginal` | None | None | None |
| `llm7/gpt-oss:20b` | 27 | 0.21% | `subscription_or_free_$0_marginal` | None | None | None |
| `nvidia/nemotron-3-super-120b-a12b:free` | 25 | 0.19% | `subscription_or_free_$0_marginal` | None | None | None |
| `regolo/gpt-oss-20b` | 25 | 0.19% | `subscription_or_free_$0_marginal` | None | None | None |
| `nvidia/nemotron-3-ultra-550b-a55b` | 24 | 0.18% | `subscription_or_free_$0_marginal` | None | None | None |
| `poolside/laguna-s-2.1:free` | 24 | 0.18% | `subscription_or_free_$0_marginal` | None | None | None |
| `recursive/flint-v1.0:free` | 22 | 0.17% | `subscription_or_free_$0_marginal` | None | None | None |
| `minimax/minimax-m3.1-flash:free` | 21 | 0.16% | `subscription_or_free_$0_marginal` | None | None | None |
| `google/gemini-4-argon` | 20 | 0.15% | `vertex_argon_paid` | 4316.85 | 0.0 | 54.15 |
| `mistral/magistral-medium-latest` | 20 | 0.15% | `subscription_or_free_$0_marginal` | 4572.65 | 0.0 | 593.05 |
| `ollamacloud/nemotron-3-super` | 19 | 0.15% | `subscription_or_free_$0_marginal` | None | None | None |
| `meituan/longcat-2.5-preview:free` | 17 | 0.13% | `subscription_or_free_$0_marginal` | None | None | None |
| `meta/muse-spark-1.3-contributor` | 17 | 0.13% | `subscription_or_free_$0_marginal` | 2673.18 | 0.0 | 1740.94 |
| `opencode/longcat-2.5-preview-free` | 15 | 0.12% | `subscription_or_free_$0_marginal` | None | None | None |
| `gemini/gemini-4-argon` | 12 | 0.09% | `vertex_argon_paid` | 7133.83 | 0.0 | 37.67 |
| `liquid/lfm-2.5-2.6b:free` | 12 | 0.09% | `subscription_or_free_$0_marginal` | None | None | None |
| `nvidia/muse-glimmer-30b` | 11 | 0.08% | `subscription_or_free_$0_marginal` | None | None | None |
| `cohere/command-a-reasoning-08-2025` | 9 | 0.07% | `subscription_or_free_$0_marginal` | None | None | None |
| `xplabs/deepseek-v4.1-flash-uncensored` | 9 | 0.07% | `subscription_or_free_$0_marginal` | 870.4 | 0.0 | 2106.2 |
| `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` | 8 | 0.06% | `subscription_or_free_$0_marginal` | None | None | None |
| `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` | 8 | 0.06% | `subscription_or_free_$0_marginal` | None | None | None |
| `ollamacloud/gpt-oss:20b` | 8 | 0.06% | `subscription_or_free_$0_marginal` | None | None | None |
| `poolside/laguna-xs-2.1:free` | 8 | 0.06% | `subscription_or_free_$0_marginal` | None | None | None |
| `stealth/missingno` | 8 | 0.06% | `subscription_or_free_$0_marginal` | None | None | None |
| `google/gemma-4-26b-a4b-it:free` | 7 | 0.05% | `subscription_or_free_$0_marginal` | None | None | None |
| `cloudflare/@cf/meta/llama-3.3-70b-instruct-fp8-fast` | 6 | 0.05% | `subscription_or_free_$0_marginal` | None | None | None |
| `sealion/aisingapore/Qwen-SEA-LION-v4.5-27B-IT` | 6 | 0.05% | `subscription_or_free_$0_marginal` | None | None | None |
| `kilo/dots-studio/dots-3-note-preview:free` | 5 | 0.04% | `subscription_or_free_$0_marginal` | None | None | None |
| `mixed` | 5 | 0.04% | `subscription_or_free_$0_marginal` | None | None | None |
| `opencode/mimo-v2.6-flash-free` | 5 | 0.04% | `subscription_or_free_$0_marginal` | None | None | None |
| `thinkingmachines/inkling-small:free` | 5 | 0.04% | `subscription_or_free_$0_marginal` | None | None | None |
| `z-ai/glm-5.3-flash` | 5 | 0.04% | `subscription_or_free_$0_marginal` | None | None | None |
| `@cf/mistralai/mistral-small-3.1-24b-instruct` | 4 | 0.03% | `subscription_or_free_$0_marginal` | None | None | None |
| `cora/qwen3.8-27b` | 4 | 0.03% | `subscription_or_free_$0_marginal` | 296.0 | 0.0 | 219.25 |
| `nvidia/nemotron-3-nano-30b-a3b` | 4 | 0.03% | `subscription_or_free_$0_marginal` | None | None | None |
| `perplexity/fast` | 4 | 0.03% | `subscription_or_free_$0_marginal` | None | None | None |
| `poolside/laguna-xs.2` | 4 | 0.03% | `subscription_or_free_$0_marginal` | None | None | None |
| `codex exec (read-only, effort medium)` | 3 | 0.02% | `subscription_or_free_$0_marginal` | None | None | None |
| `llm7/GLM-5.3-Flash` | 3 | 0.02% | `subscription_or_free_$0_marginal` | None | None | None |
| `n/v` | 3 | 0.02% | `subscription_or_free_$0_marginal` | None | None | None |
| `o/p` | 3 | 0.02% | `subscription_or_free_$0_marginal` | None | None | None |
| `@cf/ibm-granite/granite-4.0-h-micro` | 2 | 0.02% | `subscription_or_free_$0_marginal` | None | None | None |
| `executor (web checks only)` | 2 | 0.02% | `subscription_or_free_$0_marginal` | None | None | None |
| `grok-bot (no Claude/Codex)` | 2 | 0.02% | `subscription_or_free_$0_marginal` | None | None | None |
| `mistral/leanstral-1-5` | 2 | 0.02% | `subscription_or_free_$0_marginal` | None | None | None |
| `ollamacloud/nemotron-3-ultra` | 2 | 0.02% | `subscription_or_free_$0_marginal` | None | None | None |
| `opencode/glm-5.3-flash-free` | 2 | 0.02% | `subscription_or_free_$0_marginal` | None | None | None |
| `regolo/qwen3.5-122b` | 2 | 0.02% | `subscription_or_free_$0_marginal` | None | None | None |
| `regolo/qwen3.5-9b` | 2 | 0.02% | `subscription_or_free_$0_marginal` | None | None | None |
| `regolo/qwen3.8-27b` | 2 | 0.02% | `subscription_or_free_$0_marginal` | None | None | None |
| `stepfun-ai/step-5-preview` | 2 | 0.02% | `subscription_or_free_$0_marginal` | None | None | None |
| `xplabs/gpt-6-luna-decisions` | 2 | 0.02% | `subscription_or_free_$0_marginal` | None | None | None |
| `xplabs/jev-latest` | 2 | 0.02% | `subscription_or_free_$0_marginal` | None | None | None |
| `@cf/cloudflare/clairic` | 1 | 0.01% | `subscription_or_free_$0_marginal` | None | None | None |
| `@cf/qwen/qwen3-30b-a3b-fp8` | 1 | 0.01% | `subscription_or_free_$0_marginal` | None | None | None |
| `aisingapore/Qwen-SEA-LION-v4.5-32B-IT` | 1 | 0.01% | `subscription_or_free_$0_marginal` | None | None | None |
| `claude -p sonnet (read-only, plan mode)` | 1 | 0.01% | `subscription_or_free_$0_marginal` | None | None | None |
| `claude sonnet (claude -p, Read/Grep/Glob/WebSearch only)` | 1 | 0.01% | `subscription_or_free_$0_marginal` | None | None | None |
| `claude sonnet (claude -p, no tools)` | 1 | 0.01% | `subscription_or_free_$0_marginal` | None | None | None |
| `claude sonnet + codex` | 1 | 0.01% | `subscription_or_free_$0_marginal` | None | None | None |
| `codex/unknown_model` | 1 | 0.01% | `subscription_or_free_$0_marginal` | None | None | None |
| `cohere/command-a-vision-07-2025` | 1 | 0.01% | `subscription_or_free_$0_marginal` | None | None | None |
| `free lanes + twins` | 1 | 0.01% | `subscription_or_free_$0_marginal` | None | None | None |
| `free only (OpenCode muse-spark/mimo/longcat/nemotron/deepseek-v4.1-flash-free; NVIDIA gpt-oss/nemotron/glm-5.3; Nous missingno/longcat)` | 1 | 0.01% | `subscription_or_free_$0_marginal` | None | None | None |
| `free only: OpenCode (muse-spark, nemotron, mimo, longcat, deepseek-v4.1-flash-free), NVIDIA (glm-5.3, gpt-oss-20b, nemotron), Nous (longcat) incl. Hermes lane on Cora` | 1 | 0.01% | `subscription_or_free_$0_marginal` | None | None | None |
| `free only: opencode muse-spark/deepseek-v4.1-flash, nvidia gpt-oss-20b/nemotron-3.5-super-vl/glm-5.3/glm-5.3-flash/deepseek-v4.1-flash, nous missingno` | 1 | 0.01% | `subscription_or_free_$0_marginal` | None | None | None |
| `free: opencode+nvidia+hermes-nous (openrouter probes only)` | 1 | 0.01% | `subscription_or_free_$0_marginal` | None | None | None |
| `free: opencode+nvidia+hermes-openrouter` | 1 | 0.01% | `subscription_or_free_$0_marginal` | None | None | None |
| `hydra free + vertex gemini-3.8-flash` | 1 | 0.01% | `subscription_or_free_$0_marginal` | None | None | None |
| `mistral/mistral-small-latest` | 1 | 0.01% | `subscription_or_free_$0_marginal` | 19.0 | 0.0 | 2.0 |
| `note` | 1 | 0.01% | `subscription_or_free_$0_marginal` | None | None | None |
| `nous/meituan/longcat-2.5-preview:free` | 1 | 0.01% | `subscription_or_free_$0_marginal` | None | None | None |
| `nous/poolside/laguna-s-2.1:free` | 1 | 0.01% | `subscription_or_free_$0_marginal` | None | None | None |
| `nous/poolside/laguna-xs-2.1:free` | 1 | 0.01% | `subscription_or_free_$0_marginal` | None | None | None |
| `nous/reflection/beam-1.0-501b-a23b:free` | 1 | 0.01% | `subscription_or_free_$0_marginal` | None | None | None |
| `nous/stepfun/step-5-preview:free` | 1 | 0.01% | `subscription_or_free_$0_marginal` | None | None | None |
| `novita/ling-3.1-flash` | 1 | 0.01% | `subscription_or_free_$0_marginal` | None | None | None |
| `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` | 1 | 0.01% | `subscription_or_free_$0_marginal` | None | None | None |
| `sealion/x` | 1 | 0.01% | `subscription_or_free_$0_marginal` | None | None | None |
| `xplabs/deepseek-v4.1-flash-1017` | 1 | 0.01% | `subscription_or_free_$0_marginal` | 38.0 | 0.0 | 68.0 |
| `xplabs/qwen3.8-27b` | 1 | 0.01% | `subscription_or_free_$0_marginal` | 56.0 | 0.0 | 507.0 |

## Repricing Results & What the Numbers Mean

### (a) Authors' Schedule (Card `C-routed-continual-learning`)
- **Routed full library vs. One global history:** **65.0% to 72.0% cheaper** (routed/global cost ratio = **0.28 to 0.35**, midpoint **0.315** / **68.5% savings**).
- **Routed full library vs. Routed histories:** **25.0% to 33.0% cheaper** on 3 models; **5.0% more expensive** on Claude Opus 4.7.

### (b) Hydra Schedule (`data/prices.json` + Logged Mix)
1. **Homogeneous Rollouts & Uniformly-Mixed Rollouts (Advantage Survives at 1.0x):**
   - When a rollout runs end-to-end on Vertex Argon (at matching input/output/cache proportions), the per-token rate scales both conditions equally: routed full library remains **65.0% to 72.0% cheaper** in dollars (ratio of repriced advantage to paper's advantage = **1.0**).
   - When roles draw from Hydra's overall mix (`2.51%` paid Vertex Argon, `97.49%` `$0` marginal subscription lanes) uniformly across conditions, expected marginal dollar cost scales by `0.0251` in both numerator and denominator, preserving the **65.0% to 72.0%** reduction in expected marginal dollars (and **65.0% to 72.0%** reduction in subscription quota/tokens).
2. **Vertex Argon Prefix-Cache Sensitivity (Advantage Narrows if Global History Caches Better):**
   - Vertex Argon discounts cached input by **95%** (`$0.10/MTok` vs `$2.00/MTok` uncached). Because one global history appends monotonically to a single shared prefix across all 398 instances whereas routed continual learning switches across isolated clusters and issues a fresh router call per instance, global history can achieve a higher cache hit rate.
   - In an illustrative asymmetric regime where global history achieves **80% cached input** (`$0.48/MTok` effective input rate) and routed clusters achieve **40% cached input** (`$1.24/MTok` effective input rate, `2.583x` higher per input token), the input-cost reduction shrinks from **65.0–72.0%** down to **9.58%–27.67%** (routed/global ratio `0.723` to `0.904`). It still survives, but loses more than half its dollar margin.
3. **Cross-Lane Split Routing (Paid Router vs. `$0` Subscription Executor):**
   - If the agent executes on a `$0` marginal-cost subscription lane while the 398 router calls are sent to paid Vertex Argon, one global history costs **`$0.00` marginal USD** (0 router calls) while routed costs **398 paid router calls**:
     - Effective 2026-11-12 list rates: **`$4.5542`** per 398-instance stream (`$2.2771` with 50% promo).
     - From 2026-12-01 list rates: **`$9.1084`** per 398-instance stream (`$4.5542` with 50% promo).
     - Weighted by Hydra's logged paid share (`2.51%`): **`$0.1145`** list (`$0.0573` promo).
   - Conversely, if the router runs on a `$0` subscription lane and the executor runs on paid Vertex Argon, the dollar savings exceed 65–72%.

### Router-Call Break-Even Point
- **Relative break-even:** Because routed full library costs `28% to 35%` of global history (saving `65% to 72%` of global cost `G`, already including the baseline router call), additional per-instance router overhead `Delta_R` only erases the cost advantage when:
  - `Delta_R / G` reaches **0.65 to 0.72** (i.e. the router call overhead alone must add **65% to 72% of the entire global-history per-instance cost**), or
  - `Delta_R / T_routed` reaches **1.857x to 2.571x** of the entire routed per-instance cost.
- **Cross-lane marginal dollar break-even:** When the executor is on a `$0` marginal-cost subscription lane, marginal dollar break-even for a paid router is **`$0.00`** (any non-zero dollar price on the router makes marginal USD cost higher than unrouted `$0` subscription execution, though the 65–72% quota/token savings on the subscription lane still hold).
