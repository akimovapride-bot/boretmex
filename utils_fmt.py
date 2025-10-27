import html

def esc(s: str) -> str:
    return html.escape(str(s), quote=False)

def fmt_num(x, prec=8):
    try:
        n = float(x)
    except:
        return str(x)
    if abs(n) >= 1000:
        return f"{n:,.0f}".replace(",", " ")
    if abs(n) >= 1:
        return f"{n:,.2f}"
    if abs(n) >= 0.0001:
        return f"{n:.6f}".rstrip("0").rstrip(".")
    return f"{n:.8f}".rstrip("0").rstrip(".")
