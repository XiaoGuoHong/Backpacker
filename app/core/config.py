from dataclasses import dataclass, field
import os

from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _env_list(name: str, default: list[str]) -> list[str]:
    val = os.getenv(name)
    if not val:
        return list(default)
    return [item.strip() for item in val.split(",") if item.strip()]


def _env_int(name: str, default: int) -> int:
    val = os.getenv(name)
    if val is None:
        return default
    try:
        return int(val)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    val = os.getenv(name)
    if val is None:
        return default
    try:
        return float(val)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Backpacker")
    version: str = "1.0"
    environment: str = os.getenv("APP_ENV", "demo")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = _env_int("PORT", 8000)
    api_prefix: str = os.getenv("API_PREFIX", "/api/v1")
    request_timeout_seconds: float = _env_float("REQUEST_TIMEOUT_SECONDS", 10.0)

    max_input_length: int = _env_int("MAX_INPUT_LENGTH", 512)
    max_body_bytes: int = _env_int("MAX_BODY_BYTES", 1_048_576)
    rate_limit_per_minute: int = _env_int("RATE_LIMIT_PER_MINUTE", 60)
    max_results: int = _env_int("MAX_RESULTS", 20)

    # Amap
    amap_api_key: str | None = os.getenv("AMAP_API_KEY")
    amap_js_key: str | None = os.getenv("AMAP_JS_KEY")
    amap_cache_ttl: int = _env_int("AMAP_CACHE_TTL", 300)
    amap_rate_limit: float = _env_float("AMAP_RATE_LIMIT", 10.0)

    # Unsplash
    unsplash_access_key: str | None = os.getenv("UNSPLASH_ACCESS_KEY")

    # Weather
    weather_source: str = os.getenv("WEATHER_SOURCE", "open-meteo")
    weather_api_key: str | None = os.getenv("WEATHER_API_KEY")
    weather_api_url: str = os.getenv("WEATHER_API_URL", "https://devapi.qweather.com/v7/weather/3d")
    qweather_api_host: str = os.getenv("QWEATHER_API_HOST", "https://devapi.qweather.com")

    # LLM
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    llm_api_key: str | None = os.getenv("LLM_API_KEY")
    llm_model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    llm_temperature: float = _env_float("LLM_TEMPERATURE", 0.2)
    llm_available: bool = field(init=False)

    # A2A
    a2a_transport: str = os.getenv("A2A_TRANSPORT", "http")
    attraction_agent_url: str = os.getenv("ATTRACTION_AGENT_URL", "http://127.0.0.1:8002/tasks/send")
    weather_agent_url: str = os.getenv("WEATHER_AGENT_URL", "http://127.0.0.1:8003/tasks/send")
    hotel_agent_url: str = os.getenv("HOTEL_AGENT_URL", "http://127.0.0.1:8004/tasks/send")
    a2a_timeout_ms: int = _env_int("A2A_TIMEOUT_MS", 12000)

    # MCP
    mcp_transport: str = os.getenv("MCP_TRANSPORT", "streamable-http")
    amap_mcp_url: str = os.getenv("AMAP_MCP_URL", "http://127.0.0.1:8001/mcp")
    mcp_http_path: str = os.getenv("MCP_HTTP_PATH", "/mcp")

    # DB (只读，保留)
    db_enabled: bool = _env_bool("DB_ENABLED", False)
    db_path: str | None = os.getenv("DB_PATH")
    db_allowed_tables: list[str] = field(
        default_factory=lambda: _env_list("DB_ALLOWED_TABLES", ["city_weather_cache", "city_info"])
    )
    db_max_rows: int = _env_int("DB_MAX_ROWS", 100)
    db_query_timeout_ms: int = _env_int("DB_QUERY_TIMEOUT_MS", 3000)

    def __post_init__(self) -> None:
        object.__setattr__(self, "llm_available", bool(self.llm_api_key))

    @property
    def amap_available(self) -> bool:
        return bool(self.amap_api_key)

    @property
    def unsplash_available(self) -> bool:
        return bool(self.unsplash_access_key)


def get_settings() -> Settings:
    return Settings()
