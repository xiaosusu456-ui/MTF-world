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
    offset = request.args.get('offset', 0) # 接收偏移量
    limit = request.args.get('limit', 10)  # 接收每页数量
    
    if not query:
        return jsonify({"results": []})
        
    headers = {"Authorization": f"Bearer {TOKEN}"}
    params = {
        "q": query,
        "offset": offset,
        "limit": limit
    }
    
    try:
        resp = requests.get(API_URL, params=params, headers=headers, timeout=10)
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500
