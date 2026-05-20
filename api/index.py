from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)

# ========== 双实例配置 (同构 API) ==========
# 1. 实例 A (Desuwa 主站 - GET)
API_A = "https://2345.desuwa.org/api/search"
TOKEN_A = "T0MQ1gyMo2J5AN65xK6B3VJmRhV0aBAtTNn_JuEtRBY"

# 2. 实例 B (跨环 备份站 - GET)
API_B = "https://search.transcircle.org/api/search"
TOKEN_B = "mmILttPgObLRhUVw-Q8azTYkMLsGhFYZy79vIW8rW9E"


@app.route('/search')
def search():
    # 接收前端所有的筛选参数
    query = request.args.get('q', '')
    limit = request.args.get('limit', 20)
    offset = request.args.get('offset', 0)
    lang = request.args.get('lang', 'all')
    script = request.args.get('script', 'all')
    domain = request.args.get('domain', '')
    tags = request.args.get('tags', '')
    
    if not query:
        return jsonify({"results": [], "total": 0})

    # 两个实例通用的参数包
    params = {
        "q": query,
        "limit": limit,
        "offset": offset,
        "lang": lang,
        "script": script,
        "domain": domain,
        "tags": tags
    }

    # ================== 第一路：尝试请求 实例 A (Desuwa) ==================
    try:
        headers_a = {"Authorization": f"Bearer {TOKEN_A}"}
        resp = requests.get(API_A, params=params, headers=headers_a, timeout=5)
        
        if resp.status_code == 200:
            return jsonify(resp.json())
        else:
            print(f"实例 A 返回异常码 {resp.status_code}，正在自动切换至实例 B...")
    except Exception as e:
        print(f"实例 A 请求异常: {str(e)}，正在自动切换至实例 B...")


    # ================== 第二路：无缝切换至 实例 B (跨环) ==================
    try:
        headers_b = {"Authorization": f"Bearer {TOKEN_B}"}
        resp_b = requests.get(API_B, params=params, headers=headers_b, timeout=5)
        
        if resp_b.status_code == 200:
            print("成功无缝切换至 实例 B (TransCircle)")
            return jsonify(resp_b.json())
        else:
            return jsonify({"error": f"主备实例均失效。实例 B 状态码: {resp_b.status_code}"}), resp_b.status_code
            
    except Exception as e:
        return jsonify({"error": f"主备实例均请求失败。实例 B 异常: {str(e)}"}), 500        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Vercel 环境下不需要 app.run()
