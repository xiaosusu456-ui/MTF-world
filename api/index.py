from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)

# 你的 Token 和 目标 API
TOKEN = "T0MQ1gyMo2J5AN65xK6B3VJmRhV0aBAtTNn_JuEtRBY"
API_URL = "https://2345.desuwa.org/api/search"

@app.route('/search')
def search():
    # 1. 接收前端传来的所有可能参数，并设置默认值
    params = {
        "q": request.args.get('q', ''),
        "limit": request.args.get('limit', 20),   # 文档说上限是20
        "offset": request.args.get('offset', 0),
        "lang": request.args.get('lang', 'all'),
        "script": request.args.get('script', 'all'),
        "domain": request.args.get('domain', ''),
        "tags": request.args.get('tags', '')
    }
    
    # 搜索词必填检查
    if not params["q"]:
        return jsonify({"results": [], "total": 0})
        
    headers = {"Authorization": f"Bearer {TOKEN}"}
    
    try:
        # 2. 将这整套参数转发给原始 API
        resp = requests.get(API_URL, params=params, headers=headers, timeout=10)
        
        # 3. 将结果原封不动返回给前端
        return jsonify(resp.json())
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Vercel 环境下不需要 app.run()
