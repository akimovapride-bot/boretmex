import os
import json
from textwrap import dedent

# Здесь простой адаптер. Если у тебя уже подключена реальная LLM — оставь свои вызовы.
# Этот модуль формирует читабельный итог на основе снапшота, даже без внешнего API.

MODEL_NAME = os.getenv("AI_MODEL", "gpt-4")  # для инфо в тесте

def _fmt_row(r):
    return f"{r['symbol']}: Δ {r['change_pct']:.2f}% | V {r['quote_volume']:.0f} | P {r['last_price']}"

def analyze_market(snapshot: dict) -> str:
    """
    snapshot:
      {
        generated_at: ms,
        top_gainers: [{symbol, change_pct, quote_volume, last_price, vola}, ...],
        top_losers:  ...
        top_volume:  ...
        top_vola:    ...
      }
    """
    tg = "\n".join(_fmt_row(x) for x in snapshot.get("top_gainers", []))
    tl = "\n".join(_fmt_row(x) for x in snapshot.get("top_losers", []))
    tv = "\n".join(_fmt_row(x) for x in snapshot.get("top_volume", []))
    vv = "\n".join(_fmt_row(x) for x in snapshot.get("top_vola", []))

    ideas = []
    # простые эвристики на основе снапшота
    if snapshot.get("top_gainers"):
        first = snapshot["top_gainers"][0]
        ideas.append({
            "symbol": first["symbol"],
            "entry": first["last_price"],
            "sl": round(first["last_price"]*0.96, 10),
            "tp": round(first["last_price"]*1.06, 10),
            "why": "Лидер роста 24ч с повышенным интересом, пробой импульса."
        })
    if snapshot.get("top_volume"):
        firstv = snapshot["top_volume"][0]
        if firstv["symbol"] != (ideas[0]["symbol"] if ideas else ""):
            ideas.append({
                "symbol": firstv["symbol"],
                "entry": firstv["last_price"],
                "sl": round(firstv["last_price"]*0.985, 10),
                "tp": round(firstv["last_price"]*1.02, 10),
                "why": "Сильный объём — вероятно продолжение движения."
            })

    # Формируем отчёт
    report = dedent(f"""
    1) Выводы по рынку
    • Топ рост:
    {tg or "—"}
    • Топ падение:
    {tl or "—"}
    • Топ объём:
    {tv or "—"}
    • Топ волатильность:
    {vv or "—"}

    2) Предложения по сделкам
    """).strip()

    if not ideas:
        report += "\n• Сейчас явных сделок нет. Подождём более сильного сигнала."
    else:
        for i, idea in enumerate(ideas, 1):
            report += (
                f"\n• Сделка {i}: {idea['symbol']} | вход {idea['entry']} | стоп {idea['sl']} | тейк {idea['tp']}"
                f"\n  Обоснование: {idea['why']}"
            )

    report += dedent("""

    3) Риски
    • Крипторынок волатилен; обязательно использовать стоп-лосс.
    • Не входить объёмом > 2–5% депозита без подтверждающих сигналов.
    """)
    return report

def ai_smoke_test() -> str:
    return "OK"
