import asyncio
import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from main import build_portfolio_snapshot, bot
from balance_history import add_point
from signals_engine import shortlist
from mexc_client import get_exchange_info
from ai_analyzer import ai_market_review

_scheduler = None

def list_usdt_symbols(limit: int = 40) -> list[str]:
    info = get_exchange_info()
    syms = []
    for s in info.get("symbols", []):
        status = str(s.get("status", "")).upper()
        if s.get("quoteAsset") == "USDT" and status in ("ENABLED", "TRADING", "OPEN"):
            syms.append(s["symbol"])
    return syms[:limit]

def start_scheduler(chat_ids: list[int]):
    global _scheduler
    if _scheduler:
        return _scheduler
    _scheduler = AsyncIOScheduler(timezone=os.getenv("TZ", "UTC"))
    _scheduler.add_job(send_hourly_report, "cron", minute=0, args=[chat_ids])
    _scheduler.start()
    return _scheduler

async def send_hourly_report(chat_ids: list[int]):
    try:
        text, total_usdt = await asyncio.to_thread(build_portfolio_snapshot)
        add_point(total_usdt)

        syms = await asyncio.to_thread(list_usdt_symbols, 40)
        strong = await asyncio.to_thread(shortlist, syms, 0.68, 7)

        ai_text = await asyncio.to_thread(ai_market_review, text, strong)

        for cid in chat_ids:
            try:
                await bot.send_message(cid, "Ежечасный отчет")
                await bot.send_message(cid, text)
                if strong:
                    best = "\n".join([f"{i+1}. {x['symbol']} score {x['score']:.2f} votes {x['votes']}/{x['total_tools']}" for i, x in enumerate(strong)])
                    await bot.send_message(cid, "Сильные сигналы")
                    await bot.send_message(cid, best)
                await bot.send_message(cid, "AI обзор")
                await bot.send_message(cid, ai_text)
            except Exception:
                pass
    except Exception as e:
        for cid in chat_ids:
            try:
                await bot.send_message(cid, f"Ошибка отчета {e}")
            except Exception:
                pass
