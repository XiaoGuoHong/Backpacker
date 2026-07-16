"""Shared pytest configuration.

Forces deterministic test inputs by ignoring user-provided secrets in the
local `.env` (AMAP_API_KEY / AMAP_JS_KEY / UNSPLASH_ACCESS_KEY /
WEATHER_API_KEY / LLM_API_KEY). Tests construct `Settings` explicitly and
expect "no key" fallbacks to demo data.
"""
import os

# 用空字符串而非 pop：dotenv 默认 override=False，已存在的值不会被
# .env 重新覆盖，从而屏蔽本地 .env 中的真实密钥，确保测试走 demo 回退。
for _name in (
    "AMAP_API_KEY",
    "AMAP_JS_KEY",
    "UNSPLASH_ACCESS_KEY",
    "WEATHER_API_KEY",
    "LLM_API_KEY",
    "LLM_BASE_URL",
):
    os.environ[_name] = ""

# 天气也走 demo，避免测试依赖真实网络（Open-Meteo 在历史日期会走超时网络往返）
os.environ["WEATHER_SOURCE"] = "demo"