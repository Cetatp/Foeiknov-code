import os
from dotenv import load_dotenv
# 加载 backend/.env（与 config.py 读取同一文件），LANGCHAIN_API_KEY 从中注入，不硬编码
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))
os.environ.setdefault('LANGCHAIN_TRACING_V2', 'true')
os.environ.setdefault('LANGCHAIN_PROJECT', 'chengdu-travel-agent')
os.environ.setdefault('LANGCHAIN_ENDPOINT', 'https://api.smith.langchain.com')
import sys, uvicorn
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)
print(f'LAUNCH env: TRACING={os.environ.get("LANGCHAIN_TRACING_V2")} KEY_SET={bool(os.environ.get("LANGCHAIN_API_KEY"))}', flush=True)
uvicorn.run('main:app', host='0.0.0.0', port=8000, log_level='info')
