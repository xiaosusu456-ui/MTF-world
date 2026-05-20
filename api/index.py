from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import concurrent.futures

app = Flask(__name__)
CORS(app)

# ========== 双路同构 API 配置 (完美一致) ==========
# 1. 主站 (Desuwa)
API_A = "https://2345.desuwa.org/api/search"
TOKEN_A = "T0MQ1gyMo2J5AN65xK6B3VJmRhV0aBAtTNn_JuEtRBY"

# 2. 备份站 (跨环 - 经文档确认，与主站接口完全一致)
API_B = "https://search.transcircle.org/api/search"
TOKEN_B = "mmILttPgObLRhUVw-Q8azTYkMLsGhFYZy79vIW8rW9E"


@app.route('/search')
def search():
    query = request.args.get('q', '').strip()
    limit = int(request.args.get('limit', 20))
    offset = int(request.args.get('offset', 0))
    lang = request.args.get('lang', 'all')
    script = request.args.get('script', 'all')
    domain = request.args.get('domain', '').strip()
    tags = request.args.get('tags', '').strip()
    mode = request.args.get('mode', 'quota')
    
    if not query:
        return jsonify({"results": [], "total": 0})

    # 通用过滤参数（非空处理）
    params = {
        "q": query,
        "lang": lang,
        "script": script
    }
    if domain: params["domain"] = domain
    if tags: params["tags"] = tags

    # ================== 1. 次数优先模式 (串行热备) ==================
    if mode == 'quota':
        p = params.copy()
        p["limit"] = limit
        p["offset"] = offset
        
        # 尝试主站
        try:
            headers_a = {"Authorization": f"Bearer {TOKEN_A}"}
            resp = requests.get(API_A, params=p, headers=headers_a, timeout=4)
            if resp.status_code == 200:
                return jsonify(resp.json())
        except Exception:
            pass

        # 尝试备份站
        try:
            headers_b = {"Authorization": f"Bearer {TOKEN_B}"}
            resp_b = requests.get(API_B, params=p, headers=headers_b, timeout=4)
            if resp_b.status_code == 200:
                return jsonify(resp_b.json())
            else:
                return jsonify({"error": "主备服务器均异常"}), resp_b.status_code
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ================== 2. 效率优先模式 (并发拉取 4 页/40 条) ==================
    elif mode == 'speed':
        
        # 统一的极速拉取子函数
        def fetch_instance(api_url, token, offset_val):
            p = params.copy()
            p["limit"] = 20  # 强制单路最大拉取 20 条
            p["offset"] = offset_val
            headers = {"Authorization": f"Bearer {token}"}
            try:
                r = requests.get(api_url, params=p, headers=headers, timeout=4)
                if r.status_code == 200:
                    return r.json().get("results", [])
            except Exception:
                pass
            return []

        # 开启多线程并发
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            # 线程 A：去主站拿前 20 条 (第 1-2 页)
            future_a = executor.submit(fetch_instance, API_A, TOKEN_A, offset)
            # 线程 B：同时去备份站拿后 20 条 (第 3-4 页)
            future_b = executor.submit(fetch_instance, API_B, TOKEN_B, offset + 20)

            results_a = future_a.result()
            results_b = future_b.result()

        # 合并两路，完成 40 条数据拼装
        combined = results_a + results_b
        return jsonify({
            "results": combined,
            "total": len(combined)
        })
