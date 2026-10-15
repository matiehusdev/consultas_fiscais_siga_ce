import os
from pathlib import Path
from pydantic import BaseModel, Field

# Diretório raiz do projeto (siga_fiscal)
BASE_DIR = Path(__file__).resolve().parent.parent

def _load_env_file(env_path: Path):
    """Carregador simples de variáveis .env sem dependências extras."""
    if not env_path.exists():
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key not in os.environ:
                os.environ[key] = val

_load_env_file(BASE_DIR / ".env")

class Settings(BaseModel):
    app_env: str = Field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    app_host: str = Field(default_factory=lambda: os.getenv("APP_HOST", "127.0.0.1"))
    app_port: int = Field(default_factory=lambda: int(os.getenv("APP_PORT", "8000")))
    debug: bool = Field(default_factory=lambda: os.getenv("DEBUG", "true").lower() in ("1", "true", "yes"))

    # Diretórios
    base_dir: Path = BASE_DIR
    data_dir: Path = Field(default_factory=lambda: BASE_DIR / os.getenv("DATA_DIR", "data"))
    database_path: Path = Field(default_factory=lambda: BASE_DIR / os.getenv("DATABASE_PATH", "data/db/siga_fiscal.db"))
    consultas_dir: Path = Field(default_factory=lambda: BASE_DIR / os.getenv("CONSULTAS_DIR", "data/consultas"))
    empresas_dir: Path = Field(default_factory=lambda: BASE_DIR / os.getenv("EMPRESAS_DIR", "data/empresas"))
    certificados_dir: Path = Field(default_factory=lambda: BASE_DIR / os.getenv("DATA_DIR", "data") / "certificados")

    # Automação SIGA / Browser
    browser_headless: bool = Field(default_factory=lambda: os.getenv("BROWSER_HEADLESS", "false").lower() in ("1", "true", "yes"))
    browser_slow_mo_ms: int = Field(default_factory=lambda: int(os.getenv("BROWSER_SLOW_MO_MS", "100")))
    certificate_selection_timeout_seconds: int = Field(default_factory=lambda: int(os.getenv("CERTIFICATE_SELECTION_TIMEOUT_SECONDS", "120")))
    polling_interval_seconds: int = Field(default_factory=lambda: int(os.getenv("POLLING_INTERVAL_SECONDS", "5")))
    max_polling_attempts: int = Field(default_factory=lambda: int(os.getenv("MAX_POLLING_ATTEMPTS", "60")))
    page_timeout_ms: int = Field(default_factory=lambda: int(os.getenv("PAGE_TIMEOUT_MS", "60000")))

    # URL Base do SIGA
    siga_base_url: str = Field(default_factory=lambda: os.getenv("SIGA_BASE_URL", "https://siga.sefaz.ce.gov.br"))

    def ensure_directories(self) -> None:
        """Garante que todas as pastas de dados e arquivos existam."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.consultas_dir.mkdir(parents=True, exist_ok=True)
        self.empresas_dir.mkdir(parents=True, exist_ok=True)
        self.certificados_dir.mkdir(parents=True, exist_ok=True)

settings = Settings()
settings.ensure_directories()
