# -*- coding: utf-8 -*-
import re
from typing import List, Dict

Deal = Dict[str, str]  # {'symbol': 'BTCUSDT', 'entry': '...', 'stop': '...', 'take': '...', 'reason': '...'}

def parse_ai_deals(text: str) -> List[Deal]:
    """
    Парсит сделки из AI-обзора. Поддерживает два формата:
    1) Явные блоки:
       Сделка 1:
       - Символ: BTCUSDT
       - Точка входа: 65000
       - Стоп: 64000
       - Тейк: 67000
       - Обоснование: ...
    2) Внятные предложения в одну строку: "Купить BTCUSDT по рынку", "Buy BTCUSDT" и т.п.
    """
    deals: List[Deal] = []

    # Вариант 1: блочный (Сделка ...)
    block_re = re.compile(
        r"Сделка\s+\d+\s*:\s*(?:\n|\r\n|\r)"
        r"(?:.*?Символ:\s*(?P<symbol>[A-Z0-9/._-]+).*?)?"
        r"(?:.*?Точка\s*входа:\s*(?P<entry>[\d.]+).*?)?"
        r"(?:.*?Стоп:\s*(?P<stop>[\d.]+).*?)?"
        r"(?:.*?Тейк:\s*(?P<take>[\d.]+).*?)?"
        r"(?:.*?(?:Обоснование|Reason):\s*(?P<reason>.+?))?"
        , re.IGNORECASE | re.DOTALL
    )
    for m in block_re.finditer(text):
        symbol = (m.group('symbol') or '').upper().replace('/', '')
        if not symbol:
            continue
        deals.append({
            'symbol': symbol,
            'entry': (m.group('entry') or '').strip(),
            'stop': (m.group('stop') or '').strip(),
            'take': (m.group('take') or '').strip(),
            'reason': (m.group('reason') or '').strip(),
        })

    # Вариант 2: односложные рекомендации «Купить XXXUSDT»
    line_re = re.compile(r"(?:Купить|Buy)\s+([A-Z0-9/._-]{3,})", re.IGNORECASE)
    for m in line_re.finditer(text):
        sym = m.group(1).upper().replace('/', '')
        if not any(d.get('symbol') == sym for d in deals):
            deals.append({'symbol': sym, 'entry': '', 'stop': '', 'take': '', 'reason': ''})

    return deals
