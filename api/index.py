from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import concurrent.futures

app = Flask(__name__)
CORS(app)

# ========== 双路不同构 API 配置 ==========
# 1. 主站 (Desuwa 自定义 GET 接口)
API_A = "https://2345.desuwa.org/api/search"
TOKEN_A = "-IoOOzo5eeZK3wpYc3SCdyQwQ5WqyfTpY8apFYcG5Sc"

# 2. 备份站 (跨环 官方原生 Meilisearch POST 接口)
# 跨环是原生实例，基础路径是 /api/，标准检索路径是 /api/indexes/pages/search
API_B = "https://search.transcircle.org/api/indexes/pages/search"
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

    # 通用过滤参数
    params = {
        "q": query,
        "lang": lang,
        "script": script
    }
    if domain: params["domain"] = domain
    if tags: params["tags"] = tags

    # ================== 1. 次数优先模式 (串行热备，仅消耗 1 次额度) ==================
    if mode == 'quota':
        # 尝试主站 (GET)
        try:
            p = params.copy()
            p["limit"] = limit
            p["offset"] = offset
            headers = {"Authorization": f"Bearer {TOKEN_A}"}
            resp = requests.get(API_A, params=p, headers=headers, timeout=5)
            if resp.status_code == 200:
                return jsonify(resp.json())
        except Exception:
            pass

        # 主站失效，降级至备份站 (POST)
        try:
            headers_b = {
                "Authorization": f"Bearer {TOKEN_B}",
                "Content-Type": "application/json"
            }
            json_data = {
                "q": query, "limit": limit, "offset": offset,
                "attributesToHighlight": ["title", "content"]
            }
            # 拼接 Meilisearch 过滤器
            filters = []
            if domain: filters.append(f"domain = '{domain}'")
            if lang and lang != 'all': filters.append(f"lang = '{lang}'")
            if filters: json_data["filter"] = " AND ".join(filters)

            resp_b = requests.post(API_B, json=json_data, headers=headers_b, timeout=5)
            if resp_b.status_code == 200:
                raw_data = resp_b.json()
                return jsonify({
                    "results": raw_data.get("hits", []),
                    "total": raw_data.get("totalHits", len(raw_data.get("hits", [])))
                })
        except Exception as e:
            return jsonify({"error": f"两路均失败: {str(e)}"}), 500

    # ================== 2. 效率优先模式 (双路并发，拉取 40 条/4 页) ==================
    elif mode == 'speed':
        
        # 线程 A：请求主站 (GET)
        def fetch_a(offset_val):
            p = params.copy()
            p["limit"] = 20
            p["offset"] = offset_val
            headers = {"Authorization": f"Bearer {TOKEN_A}"}
            try:
                r = requests.get(API_A, params=p, headers=headers, timeout=5)
                if r.status_code == 200:
                    return r.json().get("results", [])
            except Exception:
                pass
            return []

        # 线程 B：请求备份站 (POST)
        def fetch_b(offset_val):
            headers = {
                "Authorization": f"Bearer {TOKEN_B}",
                "Content-Type": "application/json"
            }
            json_data = {
                "q": query, "limit": 20, "offset": offset_val,
                "attributesToHighlight": ["title", "content"]
            }
            filters = []
            if domain: filters.append(f"domain = '{domain}'")
            if lang and lang != 'all': filters.append(f"lang = '{lang}'")
            if filters: json_data["filter"] = " AND ".join(filters)
            
            try:
                r = requests.post(API_B, json=json_data, headers=headers, timeout=5)
                if r.status_code == 200:
                    # 原生返回的是 hits，直接在这里作为结果返回
                    return r.json().get("hits", [])
            except Exception:
                pass
            return []

        # 并发执行
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_a = executor.submit(fetch_a, offset)
            future_b = executor.submit(fetch_b, offset + 20)

            results_a = future_a.result()
            results_b = future_b.result()

        combined = results_a + results_b
        return jsonify({
            "results": combined,
            "total": len(combined)
        })

    return jsonify({"results": [], "total": 0})
