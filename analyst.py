"""
analyst.py
----------
Fully synchronous — calls the Experiential Labs API (Anthropic-compatible)
with web_search enabled. Designed to run inside a thread executor from the async bot.

Base URL : https://api.experientiallabs.ai/v1
Model    : claude-fable-5.1
Auth     : EXPLABS_API_KEY environment variable
"""

import os
import datetime
import logging
import anthropic

log = logging.getLogger(__name__)

EXPLABS_BASE_URL = "https://api.experientiallabs.ai"
MODEL_ID         = "claude-fable-5.1"

SYSTEM_PROMPT = """You are a professional morning market analyst for an active options swing trader.

Every time you run, follow these steps IN ORDER — never skip step 1:

## STEP 1 — Research (mandatory, do before writing anything)
Use the web_search tool to gather:
- S&P 500 / Nasdaq / Dow futures premarket today
- VIX level today
- CNN Fear & Greed Index current reading
- Macro events today (CPI, PPI, FOMC, jobs, Fed speakers)
- Top gaining/losing sectors premarket today
- Unusual options activity / large sweeps today
- Biggest premarket movers today
- Key individual stock news for any major catalysts (earnings, upgrades, events)

Search at least 6-8 times across different queries before writing output.
Never fabricate data — if unavailable, note it explicitly.

## STEP 2 — Market Overview
Write a concise header block:
- Index levels (SPY/QQQ/IWM % change)
- VIX and direction
- Fear & Greed score and label
- Macro events today
- Overall bias: BULLISH / BEARISH / NEUTRAL + one-line reason
- 2-4 sentence narrative

## STEP 3 — 10 Options Picks
Single-leg calls/puts only. 1-5 DTE swing plays.

For each pick:
- Score internally on: catalyst clarity, technical alignment, options flow, volume (only include 8+/12)
- Format each pick with: thesis, signal confluence (news/technical/flow/volume), and a trade setup table with strike, expiry, entry range, target (+75-100%), stop (-50%), hold period
- Add risk flags

## STEP 4 — Quick Reference Table
All 10 picks in one summary table with conviction stars.

## STEP 5 — Risk Reminder
End with the standard risk disclaimer.

## Style
- Direct, Bloomberg-analyst tone
- Use trader vocab naturally
- Never pad with weak setups
- Format for Telegram: use *bold* for headers, avoid HTML tags"""


def get_client() -> anthropic.Anthropic:
    """
    Build and return the Anthropic-compatible client pointed at Experiential Labs.
    Raises a clear error if EXPLABS_API_KEY is not set.
    """
    api_key = os.environ.get("EXPLABS_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "EXPLABS_API_KEY is not set. "
            "Please create one under Settings → API Keys and add it as a Railway environment variable."
        )
    return anthropic.Anthropic(
        api_key=api_key,
        base_url=EXPLABS_BASE_URL,
    )


def run_morning_analysis_sync() -> str:
    """
    Pure synchronous function — safe to call from thread executor.
    """
    log.info("analyst: creating Experiential Labs client")
    client = get_client()

    today = datetime.date.today().strftime("%B %d, %Y")
    log.info(f"analyst: calling {MODEL_ID} for {today}")

    try:
        response = client.messages.create(
            model=MODEL_ID,
            max_tokens=8000,
            system=SYSTEM_PROMPT,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{
                "role": "user",
                "content": (
                    f"Run the full morning market analysis for {today}. "
                    "Search for live data first, then produce the complete briefing "
                    "with 10 options picks, trade setups, and the summary table."
                )
            }]
        )
        log.info(f"analyst: done — stop_reason={response.stop_reason}, blocks={len(response.content)}")

        output_parts = []
        for block in response.content:
            if hasattr(block, "text"):
                output_parts.append(block.text)
                log.info(f"analyst: text block {len(block.text)} chars")

        result = "\n\n".join(output_parts) if output_parts else "No output generated."
        log.info(f"analyst: returning {len(result)} chars total")
        return result

    except EnvironmentError:
        raise
    except Exception as e:
        log.error(f"analyst: API error — {type(e).__name__}: {e}")
        raise


async def run_morning_analysis() -> str:
    return run_morning_analysis_sync()
