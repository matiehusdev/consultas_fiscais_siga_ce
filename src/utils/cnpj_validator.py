import re
from typing import Tuple

def clean_cnpj(cnpj: str) -> str:
    """Remove pontuação e caracteres não numéricos."""
    if not cnpj:
        return ""
    return re.sub(r"\D", "", str(cnpj))

def format_cnpj(cnpj: str) -> str:
    """Formata CNPJ no padrão XX.XXX.XXX/XXXX-XX."""
    cleaned = clean_cnpj(cnpj)
    if len(cleaned) != 14:
        return cnpj
    return f"{cleaned[:2]}.{cleaned[2:5]}.{cleaned[5:8]}/{cleaned[8:12]}-{cleaned[12:14]}"

def extract_cnpj_base(cnpj: str) -> str:
    """Extrai os primeiros 8 dígitos (CNPJ Base)."""
    cleaned = clean_cnpj(cnpj)
    return cleaned[:8] if len(cleaned) >= 8 else cleaned

def validate_cnpj(cnpj: str) -> Tuple[bool, str]:
    """
    Valida rigorosamente o CNPJ através do cálculo dos dígitos verificadores.
    Retorna (True, "") ou (False, "Motivo do erro").
    """
    cleaned = clean_cnpj(cnpj)

    if not cleaned:
        return False, "CNPJ não informado."

    if len(cleaned) != 14:
        return False, f"CNPJ deve conter exatamente 14 dígitos (encontrados {len(cleaned)})."

    # Rejeita sequências repetidas conhecidas (00000000000000, 11111111111111, etc.)
    if cleaned == cleaned[0] * 14:
        return False, "CNPJ inválido (dígitos repetidos)."

    # Cálculo do primeiro dígito verificador
    weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    sum1 = sum(int(cleaned[i]) * weights1[i] for i in range(12))
    remainder1 = sum1 % 11
    digit1 = 0 if remainder1 < 2 else 11 - remainder1

    if int(cleaned[12]) != digit1:
        return False, f"Primeiro dígito verificador inválido (esperado {digit1}, obtido {cleaned[12]})."

    # Cálculo do segundo dígito verificador
    weights2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    sum2 = sum(int(cleaned[i]) * weights2[i] for i in range(13))
    remainder2 = sum2 % 11
    digit2 = 0 if remainder2 < 2 else 11 - remainder2

    if int(cleaned[13]) != digit2:
        return False, f"Segundo dígito verificador inválido (esperado {digit2}, obtido {cleaned[13]})."

    return True, ""
