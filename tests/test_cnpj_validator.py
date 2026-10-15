import pytest
from src.utils.cnpj_validator import validate_cnpj, clean_cnpj, format_cnpj, extract_cnpj_base

def test_clean_cnpj():
    assert clean_cnpj("12.720.599/0001-17") == "12720599000117"
    assert clean_cnpj("12720599000117") == "12720599000117"
    assert clean_cnpj("") == ""
    assert clean_cnpj(None) == ""

def test_format_cnpj():
    assert format_cnpj("12720599000117") == "12.720.599/0001-17"
    assert format_cnpj("12.720.599/0001-17") == "12.720.599/0001-17"
    # Formato inválido não altera
    assert format_cnpj("123") == "123"

def test_extract_cnpj_base():
    assert extract_cnpj_base("12.720.599/0001-17") == "12720599"
    assert extract_cnpj_base("12720599000117") == "12720599"

def test_validate_cnpj_valid():
    # CNPJ do exemplo real fornecido pelo usuário
    is_valid, msg = validate_cnpj("12.720.599/0001-17")
    assert is_valid is True
    assert msg == ""

    # CNPJ do Banco do Brasil
    is_valid, msg = validate_cnpj("00.000.000/0001-91")
    assert is_valid is True

    # CNPJ da Petrobras
    is_valid, msg = validate_cnpj("33.000.167/0001-01")
    assert is_valid is True

def test_validate_cnpj_invalid_digits():
    # Dígito verificador incorreto
    is_valid, msg = validate_cnpj("12.720.599/0001-18")
    assert is_valid is False
    assert "dígito verificador inválido" in msg.lower()

def test_validate_cnpj_repeated_digits():
    is_valid, msg = validate_cnpj("11.111.111/1111-11")
    assert is_valid is False
    assert "repetidos" in msg.lower()

    is_valid, msg = validate_cnpj("00.000.000/0000-00")
    assert is_valid is False

def test_validate_cnpj_wrong_length():
    is_valid, msg = validate_cnpj("123456")
    assert is_valid is False
    assert "14 dígitos" in msg

    is_valid, msg = validate_cnpj("")
    assert is_valid is False
    assert "não informado" in msg
