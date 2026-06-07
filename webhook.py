"""
webhook.py
----------
FastAPI server that receives TradingView alerts and forwards them to Telegram.
Runs alongside the Telegram bot on a separate port.

TradingView Alert Message (JSON format):
{
    "symbol":    "NQ1!",
    "action":    "BUY" | "SELL" | "EXIT_LONG" | "EXIT_SHORT",
    "price":     18245.50,
    "qty":       1,
    "sl":        18200.00,
    "tp":        18350.00,
    "timeframe": "15m",
    "comment":   "NW Breakout",
    "secret":    "your_webhook_secret"
}
"""

import os
import asyncio
import logging
from datetime import datetime
from typing import Optional
import pytz

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import httpx

log = logging.getLogger(__name__)

TELEGRAM_TOKEN  = os.environ["TELEGRAM_TOKEN"]
CHAT_ID         = os.environ["CHAT_ID"]
WEBHOOK_SECRET  = os.environ.get("WEBHOOK_SECRET", "changeme123")
TIMEZONE        = os.getenv("TIMEZONE", "America/Los_Angeles")

TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

app = FastAPI(title="TradingView Alert Webhook")

# ── In-memory position tracker ─────────────────────────────────────────────────
# { "NQ1!": {"action": "BUY", "price": 18245.50, "qty": 1, "time": datetime} }
open_positions: dict = {}

# Futures contract specs for P&L calculation
CONTRACT_SPECS = {
    "NQ":  {"tick": 0.25, "tick_value": 5.00,   "currency": "USD", "name": "Nasdaq Futures"},
    "ES":  {"tick": 0.25, "tick_value": 12.50,  "currency": "USD", "name": "S&P 500 Futures"},
    "GC":  {"tick": 0.10, "tick_value": 10.00,  "currency": "USD", "name": "Gold Futures"},
}

# ── Pydantic model ─────────────────────────────────────────────────────────────

class AlertPayload(BaseModel):
    symbol:    str
    action:    str                  # BUY | SELL | EXIT_LONG | EXIT_SHORT
    price:     float
    qty:       Optional[int] = 1
    sl:        Optional[float] = None
    tp:        Optional[float] = None
    timeframe: Optional[str] = None
    comment:   Optional[str] = None
    secret:    Optional[str] = None

# ── Helpers ────────────────────────────────────────────────────────────────────

def get_base_symbol(symbol: str) -> str:
    """Extract base from 'NQ1!' → 'NQ', 'GC1!' → 'GC' etc."""
    return ''.join(filter(str.isalpha, symbol)).upper()[:2]


def calc_pnl(symbol: str, entry: float, exit_price: float, qty: int, direction: str) -> str:
    base = get_base_symbol(symbol)
    spec = CONTRACT_SPECS.get(base)
    if not spec:
        return "P&L: N/A (unknown contract)"

    ticks = abs(exit_price - entry) / spec["tick"]
    pnl   = ticks * spec["tick_value"] * qty
    if direction == "LONG":
        pnl = pnl if exit_price > entry else -pnl
    else:
        pnl = pnl if exit_price < entry else -pnl

    sign  = "+" if pnl >= 0 else ""
    emoji = "✅" if pnl >= 0 else "❌"
    return f"{emoji} P&L: {sign}${pnl:,.2f} ({ticks:.0f} ticks × ${spec['tick_value']} × {qty} contract{'s' if qty>1 else ''})"


def format_entry_alert(p: AlertPayload) -> str:
    base  = get_base_symbol(p.symbol)
    spec  = CONTRACT_SPECS.get(base, {})
    name  = spec.get("name", p.symbol)
    tz    = pytz.timezone(TIMEZONE)
    now   = datetime.now(tz).strftime("%b %d %H:%M %Z")
    dir_emoji = "🟢 LONG" if p.action == "BUY" else "🔴 SHORT"

    lines = [
        f"📡 *TradingView Alert — {name}*",
        f"`{p.symbol}` · {p.timeframe or '—'} · {now}",
        "",
        f"*{dir_emoji}  Entry @ {p.price:,.2f}*",
        f"Qty: {p.qty} contract{'s' if p.qty > 1 else ''}",
    ]
    if p.sl:
        sl_dist = abs(p.price - p.sl)
        lines.append(f"🛑 Stop Loss:   `{p.sl:,.2f}`  (–{sl_dist:.2f} pts)")
    if p.tp:
        tp_dist = abs(p.tp - p.price)
        lines.append(f"🎯 Take Profit: `{p.tp:,.2f}`  (+{tp_dist:.2f} pts)")
    if p.sl and p.tp:
        rr = abs(p.tp - p.price) / abs(p.price - p.sl)
        lines.append(f"⚖️  R:R = 1 : {rr:.1f}")
    if p.comment:
        lines.append(f"💬 _{p.comment}_")

    return "\n".join(lines)


def format_exit_alert(p: AlertPayload, entry_info: dict) -> str:
    base      = get_base_symbol(p.symbol)
    spec      = CONTRACT_SPECS.get(base, {})
    name      = spec.get("name", p.symbol)
    tz        = pytz.timezone(TIMEZONE)
    now       = datetime.now(tz).strftime("%b %d %H:%M %Z")
    direction = "LONG" if entry_info["action"] == "BUY" else "SHORT"
    pnl_str   = calc_pnl(p.symbol, entry_info["price"], p.price, p.qty, direction)

    # Duration
    held_secs = (datetime.now(pytz.utc) - entry_info["time"]).total_seconds()
    held_mins = int(held_secs // 60)
    held_str  = f"{held_mins}m" if held_mins < 60 else f"{held_mins//60}h {held_mins%60}m"

    lines = [
        f"📡 *TradingView Alert — {name}*",
        f"`{p.symbol}` · {p.timeframe or '—'} · {now}",
        "",
        f"*⬜ EXIT {direction} @ {p.price:,.2f}*",
        f"Entry was: `{entry_info['price']:,.2f}` · Held: {held_str}",
        "",
        pnl_str,
    ]
    if p.comment:
        lines.append(f"💬 _{p.comment}_")

    return "\n".join(lines)


async def send_telegram(text: str) -> None:
    async with httpx.AsyncClient() as client:
        await client.post(TELEGRAM_URL, json={
            "chat_id":    CHAT_ID,
            "text":       text,
            "parse_mode": "Markdown"
        })

# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "tradingview-webhook"}


@app.post("/alert")
async def receive_alert(payload: AlertPayload):
    # Verify secret
    if payload.secret != WEBHOOK_SECRET:
        log.warning(f"Invalid webhook secret from alert on {payload.symbol}")
        raise HTTPException(status_code=403, detail="Invalid secret")

    action = payload.action.upper()
    log.info(f"Alert received: {payload.symbol} {action} @ {payload.price}")

    is_entry = action in ("BUY", "SELL")
    is_exit  = action in ("EXIT_LONG", "EXIT_SHORT")

    if is_entry:
        # Track position
        open_positions[payload.symbol] = {
            "action": action,
            "price":  payload.price,
            "qty":    payload.qty,
            "time":   datetime.now(pytz.utc)
        }
        msg = format_entry_alert(payload)

    elif is_exit:
        entry_info = open_positions.pop(payload.symbol, None)
        if entry_info:
            msg = format_exit_alert(payload, entry_info)
        else:
            # Exit without a tracked entry — show basic alert
            direction = "LONG" if action == "EXIT_LONG" else "SHORT"
            tz  = pytz.timezone(TIMEZONE)
            now = datetime.now(tz).strftime("%b %d %H:%M %Z")
            msg = (
                f"📡 *TradingView Alert*\n"
                f"`{payload.symbol}` · {now}\n\n"
                f"*⬜ EXIT {direction} @ {payload.price:,.2f}*\n"
                f"_(No tracked entry — P&L unavailable)_"
            )
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")

    await send_telegram(msg)
    return {"status": "sent", "symbol": payload.symbol, "action": action}


@app.get("/positions")
async def get_positions():
    """Show currently tracked open positions."""
    return {"open_positions": open_positions}
