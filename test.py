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