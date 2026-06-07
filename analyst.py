"""
analyst.py
----------
Calls the Anthropic API with web_search enabled.
Claude runs the full morning-market-analyst skill and returns the briefing as text.
"""

import os
import anthropic

ANTHROPIC_KEY = os.environ["ANTHROPIC_API_KEY"]

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

Search at least 6–8 times across different queries before writing output.
Never fabricate data — if unavailable, note it explicitly.

## STEP 2 — Market Overview
Write a concise header block:
- Index levels (SPY/QQQ/IWM % change)
- VIX and direction
- Fear & Greed score and label
- Macro events today
- Overall bias: BULLISH / BEARISH / NEUTRAL + one-line reason
- 2–4 sentence narrative

## STEP 3 — 10 Options Picks
Single-leg calls/puts only. 1–5 DTE swing plays.

For each pick:
- Score internally on: catalyst clarity, technical alignment, options flow, volume (only include ≥8/12)
- Format each pick with: thesis, signal confluence (news/technical/flow/volume), and a trade setup table with strike, expiry, entry range, target (+75–100%), stop (–50%), hold period
- Add risk flags

## STEP 4 — Quick Reference Table
All 10 picks in one summary table with conviction stars (⭐⭐⭐ / ⭐⭐ / ⭐).

## STEP 5 — Risk Reminder
End with the standard risk disclaimer.

## Style
- Direct, Bloomberg-analyst tone
- Use trader vocab naturally (sweep, flush, squeeze, breakout, flow)
- Never pad with weak setups — if fewer than 10 pass the filter, say so
- Format for Telegram: use *bold* for headers, avoid HTML tags"""


async def run_morning_analysis() -> str:
    """
    Runs the morning market analyst via Claude claude-sonnet-4-20250514 with web search.
    Returns the full briefing as a plain string.
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        tools=[
            {
                "type": "web_search_20250305",
                "name": "web_search"
            }
        ],
        messages=[
            {
                "role": "user",
                "content": (
                    "Run the full morning market analysis right now. "
                    "Search for live data first, then produce the complete briefing "
                    "with 10 options picks, trade setups, and the summary table. "
                    "Today's date: " + __import__("datetime").date.today().strftime("%B %d, %Y")
                )
            }
        ]
    )

    # Extract all text blocks from the response
    output_parts = []
    for block in response.content:
        if block.type == "text":
            output_parts.append(block.text)

    return "\n\n".join(output_parts) if output_parts else "No output generated."
