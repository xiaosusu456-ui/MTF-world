from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)

TOKEN = "T0MQ1gyMo2J5AN65xK6B3VJmRhV0aBAtTNn_JuEtRBY"
API_URL = "https://2345.desuwa.org/api/search"

@app.route('/search')
def search():
    query = request.args.get('q', '')
    if not query:
        return jsonify([])
    headers = {"Authorization": f"Bearer {TOKEN}"}
    try:
        # 增加 timeout 防止手机网络波动挂起
        resp = requests.get(API_URL, params={"q": query}, headers=headers, timeout=5)
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 注意：在 PythonAnywhere 上不需要 app.run()，它是通过 WSGI 运行的
