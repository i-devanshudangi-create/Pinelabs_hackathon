import os
from dotenv import load_dotenv

load_dotenv()

PINE_LABS_BASE_URL = os.getenv("PINE_LABS_BASE_URL", "https://pluraluat.v2.pinepg.in/api")
PINE_LABS_CLIENT_ID = os.getenv("PINE_LABS_CLIENT_ID", "")
PINE_LABS_CLIENT_SECRET = os.getenv("PINE_LABS_CLIENT_SECRET", "")
PINE_LABS_MID = os.getenv("PINE_LABS_MID", "")

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_SESSION_TOKEN = os.getenv("AWS_SESSION_TOKEN", "")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0")

FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
