import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
load_dotenv()

# 读取模型名称，没有配置时使用 deepseek-chat
MODEL_NAME = os.getenv("MODEL_NAME", "deepseek-v4-flash")

model = init_chat_model(MODEL_NAME)
