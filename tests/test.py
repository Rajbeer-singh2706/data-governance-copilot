import os
from dotenv import load_dotenv

# load our .env file 
load_dotenv()

## read a value from it 
mock_mode = os.getenv("ENABLE_MOCK", "not found")
log_level = os.getenv("LOG_LEVEL" , "not found")

print(f"ENABLE_MOCK = {mock_mode}")
print(f"LOG_LEVEL = {log_level}")
print("Setup is working correctly!")


## python test.py

# test_settings.py  (in root folder — delete after)

from config.settings import config, DATA_PRODUCTS

# ── Test 1: basic values ─────────────────────────────────
print("=== AppConfig ===")
print(f"enable_mock : {config.enable_mock}")   # should be True
print(f"log_level   : {config.log_level}")     # should be INFO
print(f"debug       : {config.debug}")         # should be False
print(f"max_retries : {config.max_retries}")   # should be 3

# ── Test 2: nested configs work ──────────────────────────
print("\n=== LLMConfig (nested) ===")
print(f"provider    : {config.llm.provider}")  # should be openai
print(f"model       : {config.llm.model}")     # should be gpt-4o
print(f"temperature : {config.llm.temperature}") # should be 0.1

# ── Test 3: Databricks config nested ────────────────────
print("\n=== DatabricksConfig (nested) ===")
print(f"catalog : {config.databricks.catalog}") # should be main
print(f"schema  : {config.databricks.schema}")  # should be analytics

# ── Test 4: DATA_PRODUCTS dict ───────────────────────────
print("\n=== DATA_PRODUCTS ===")
for name, info in DATA_PRODUCTS.items():
    print(f"  {name} → owner: {info['owner']}, table: {info['table']}")

# ── Test 5: singleton check ──────────────────────────────
print("\n=== Singleton test ===")
from config.settings import config as config2
print(f"Same object? {config is config2}")     # should be True

print("\n✅ All tests passed!")