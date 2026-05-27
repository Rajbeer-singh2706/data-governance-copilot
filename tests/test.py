"""
tests/test.py — Quick smoke-test / diagnostic script.
Run directly: python tests/test.py
(Not part of the pytest suite — no pytest imports.)
"""
import os
from dotenv import load_dotenv

load_dotenv()

print("=== Environment ===")
print(f"ENVIRONMENT = {os.getenv('ENVIRONMENT', 'not set')}")
print(f"LOG_LEVEL   = {os.getenv('LOG_LEVEL', 'not set')}")
print(f"LLM_PROVIDER= {os.getenv('LLM_PROVIDER', 'not set')}")

from config.settings import config, DATA_PRODUCTS

print("\n=== AppConfig ===")
print(f"environment : {config.environment}")
print(f"log_level   : {config.log_level}")
print(f"debug       : {config.debug}")

print("\n=== LLMConfig ===")
print(f"provider    : {config.llm.provider}")
print(f"model       : {config.llm.model}")
print(f"temperature : {config.llm.temperature}")

print("\n=== DatabricksConfig ===")
print(f"host        : {config.databricks.host or '(not set)'}")
print(f"catalog     : {config.databricks.catalog}")
print(f"schema      : {config.databricks.schema}")

print("\n=== DATA_PRODUCTS ===")
for name, info in DATA_PRODUCTS.items():
    print(f"  {name} → owner: {info['owner']}, table: {info['table']}")

print("\n=== Singleton test ===")
from config.settings import config as config2
print(f"Same object? {config is config2}")

print("\n✅ Smoke test passed!")
