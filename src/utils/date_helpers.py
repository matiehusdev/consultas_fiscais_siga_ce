import re
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple, Any

NOMES_MESES: Dict[int, str] = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Março",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro"
}

MESES_ALIASES: Dict[int, List[str]] = {
    1: ["janeiro", "jan"],
    2: ["fevereiro", "fev"],
    3: ["março", "marco", "mar"],
    4: ["abril", "abr"],
    5: ["maio", "mai"],
    6: ["junho", "jun"],
    7: ["julho", "jul"],
    8: ["agosto", "ago"],
    9: ["setembro", "set"],
    10: ["outubro", "out"],
    11: ["novembro", "nov"],
    12: ["dezembro", "dez"]
}

def clean_date_str(val: Any) -> str:
    """Extrai texto limpo de data descartando horários e fusos."""
    if val is None:
        return ""
    if isinstance(val, (datetime, date)):
        return val.strftime("%Y-%m-%d")
    s = str(val).strip()
    # Se for ISO timestamp completo com T tipo 2026-09-15T14:32:10
    if re.match(r'^\d{4}-\d{2}-\d{2}[Tt]', s):
        s = s[:10]
    # Remove componentes de hora tipo " 14:32:10" ou " 14:32"
    s = re.sub(r'\s+\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?.*$', '', s)
    return s.strip()

def matches_month(mes_str: Optional[Any], target_year: int, target_month: int) -> bool:
    """
    Verifica se a descrição ou data de competência informada na planilha corresponde
    estritamente ao mês e ano alvo da consulta fiscal.
    Suporta:
    - Nomes por extenso em pt-BR ('Setembro', 'setembro', 'set')
    - Formatos numéricos ('09/2026', '2026-09', '09/26', '9', '09', 'Mês 9')
    - Datas completas com ou sem horário ('2026-09-15 14:00:00', '15/09/2026 10:30')
    - Rejeição de outros anos (ex: 'Setembro/2025' com target 2026 retorna False)
    """
    if mes_str is None:
        return False

    s = clean_date_str(mes_str).lower()
    if not s or s in ("total", "nan", "none"):
        return False

    # Normalização de caracteres corrompidos comuns em encodings (ex: "maro" -> "marco")
    s_norm = s.replace("\ufffd", "c").replace("?", "c")

    # Se contiver ano explícito de 4 dígitos, valida se bate com o target_year
    ano_match = re.search(r'\b(20\d\d)\b', s)
    if ano_match:
        ano_encontrado = int(ano_match.group(1))
        if ano_encontrado != target_year:
            return False

    # Se for formato ISO: YYYY-MM ou YYYY-MM-DD
    m_iso = re.search(r'20\d\d[-/](\d{1,2})', s)
    if m_iso:
        return int(m_iso.group(1)) == target_month

    # Se for formato brasileiro: DD/MM/YYYY ou MM/YYYY ou MM/YY
    m_br_full = re.search(r'\b\d{1,2}/(\d{1,2})/\d{2,4}\b', s)
    if m_br_full:
        return int(m_br_full.group(1)) == target_month

    m_br_simple = re.search(r'\b(\d{1,2})/\d{2,4}\b', s)
    if m_br_simple:
        return int(m_br_simple.group(1)) == target_month

    # Formatos de número de mês isolado ("09", "9", "mês 9", "mes 09")
    m_num = re.fullmatch(r'(?:m[êe]s\s*)?0?([1-9]|1[0-2])', s_norm.strip())
    if m_num:
        return int(m_num.group(1)) == target_month

    # Se for o nome do mês em português (ex: "Setembro", "set")
    termos_alvo = MESES_ALIASES.get(target_month, [])
    for termo in termos_alvo:
        if re.search(rf'\b{termo}\b', s_norm):
            return True

    return False

def matches_period(mes_str: Optional[Any], data_inicio: date, data_fim: date) -> bool:
    """
    Verifica se a competência ou data informada corresponde ao período solicitado
    (suporta consulta de 1 mês específico ou intervalo de múltiplos meses).
    """
    if mes_str is None:
        return False

    # Caso mais comum: mesmo mês e ano
    if data_inicio.year == data_fim.year and data_inicio.month == data_fim.month:
        return matches_month(mes_str, data_inicio.year, data_inicio.month)

    # Intervalo de múltiplos meses: gera todos os pares (ano, mes) entre data_inicio e data_fim
    cur_y = data_inicio.year
    cur_m = data_inicio.month
    end_y = data_fim.year
    end_m = data_fim.month

    while (cur_y < end_y) or (cur_y == end_y and cur_m <= end_m):
        if matches_month(mes_str, cur_y, cur_m):
            return True
        cur_m += 1
        if cur_m > 12:
            cur_m = 1
            cur_y += 1

    return False

def format_periodo_mes(data_inicio: date, data_fim: date) -> str:
    """
    Formata o período para exibição executiva.
    Se for um mês específico fechado, exibe ex: 'Setembro de 2026 (01/09/2026 a 30/09/2026)'.
    """
    if data_inicio.month == data_fim.month and data_inicio.year == data_fim.year:
        nome_mes = NOMES_MESES.get(data_inicio.month, "")
        return f"{nome_mes} de {data_inicio.year} ({data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')})"
    return f"{data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}"
