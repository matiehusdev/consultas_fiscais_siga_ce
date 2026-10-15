import pytest
from src.utils.sanitizers import sanitize_url, sanitize_text

def test_sanitize_url_removes_s3_tokens():
    raw_url = "https://sefaz-ce-aplicacoes-prod.s3.sa-east-1.amazonaws.com/relatorio.xlsx?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIAIOSFODNN7EXAMPLE%2F20261008%2Fsa-east-1%2Fs3%2Faws4_request&X-Amz-Signature=d2c8842c9f563&X-Amz-Security-Token=AQoDYXdzEJr111"
    clean = sanitize_url(raw_url)
    assert "d2c8842c9f563" not in clean
    assert "AKIAIOSFODNN7EXAMPLE" not in clean
    assert "AQoDYXdzEJr111" not in clean
    assert "X-Amz-Signature=%5BFILTERED%5D" in clean or "X-Amz-Signature=[FILTERED]" in clean

def test_sanitize_text_filters_passwords_and_tokens():
    raw_text = "Conectando com token: eyJhbGciOiJIUzI1NiJ9 e senha: minhasenha123"
    clean = sanitize_text(raw_text)
    assert "minhasenha123" not in clean
    assert "eyJhbGciOiJIUzI1NiJ9" not in clean
