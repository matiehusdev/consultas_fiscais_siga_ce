import re
from datetime import date
from typing import Dict, List, Optional

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

def matches_month(mes_str: Optional[str], target_year: int, target_month: int) -> bool:
    """
    Verifica se a descrição ou data de competência informada na planilha corresponde
    estritamente ao mês e ano alvo da consulta fiscal.
    Suporta:
    - Nomes por extenso em pt-BR ('Setembro', 'setembro', 'set')
    - Formatos numéricos ('09/2026', '2026-09', '09/26')
    - Datas completas ('2026-09-15', '15/09/2026')
    - Rejeição de outros anos (ex: 'Setembro/2025' com target 2026 retorna False)
    """
    if not mes_str:
        return False

    s = str(mes_str).strip().lower()

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

    # Se for apenas o nome do mês em português (ex: "Setembro", "set")
    termos_alvo = MESES_ALIASES.get(target_month, [])
    for termo in termos_alvo:
        # Garante casamento de palavra completa para evitar falsos positivos
        if re.search(rf'\b{termo}\b', s):
            return True

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
