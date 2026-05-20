from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import concurrent.futures  # 【新增】引入并发库

app = Flask(__name__)
CORS(app)

# ========== 双实例配置 (同构 API) ==========
API_A = "https://2345.desuwa.org/api/search"
TOKEN_A = "T0MQ1gyMo2J5AN65xK6B3VJmRhV0aBAtTNn_JuEtRBY"

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
    
    # 接收前端传来的模式：'quota' (次数优先) 或 'speed' (效率优先)
    mode = request.args.get('mode', 'quota')
    
    if not query:
        return jsonify({"results": [], "total": 0})

    # 通用参数包
    params = {
        "q": query,
        "lang": lang,
        "script": script
    }
    if domain: params["domain"] = domain
    if tags: params["tags"] = tags

    # ================== 模式一：次数优先 (串行热备，仅消耗 1 次额度) ==================
    if mode == 'quota':
        params["limit"] = limit
        params["offset"] = offset
        
        # 尝试主站
        try:
            headers_a = {"Authorization": f"Bearer {TOKEN_A}"}
            resp = requests.get(API_A, params=params, headers=headers_a, timeout=5)
            if resp.status_code == 200:
                return jsonify(resp.json())
        except Exception:
            pass

        # 主站失败，无缝降级备份站
        try:
            headers_b = {"Authorization": f"Bearer {TOKEN_B}"}
            resp_b = requests.get(API_B, params=params, headers=headers_b, timeout=5)
            if resp_b.status_code == 200:
                return jsonify(resp_b.json())
            else:
                return jsonify({"error": f"主备实例均失效。"}), resp_b.status_code
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ================== 模式二：效率优先 (双路并发，一次拉取 40 条/4 页，消耗 2 次额度) ==================
    elif mode == 'speed':
        # 定义一个内部线程任务：去特定实例拉取 20 条
        def fetch_task(api_url, token, offset_val):
            p = params.copy()
            p["limit"] = 20  # 强制单次上限 20
            p["offset"] = offset_val
            h = {"Authorization": f"Bearer {token}"}
            try:
                r = requests.get(api_url, params=p, headers=h, timeout=5)
                if r.status_code == 200:
                    return r.json().get("results", [])
            except Exception:
                pass
            return []

        # 开启多线程并发（ThreadPoolExecutor 非常轻量，完美适配 Vercel）
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            # 线程 1：去主站拉取前 20 条 (第 1-2 页)
            future_a = executor.submit(fetch_task, API_A, TOKEN_A, offset)
            # 线程 2：同一时间去备份站拉取后 20 条 (第 3-4 页)
            future_b = executor.submit(fetch_task, API_B, TOKEN_B, offset + 20)

            # 等待双路结果返回
            results_a = future_a.result()
            results_b = future_b.result()

        # 合并两路数据，一次性拿到 40 条结果
        combined_results = results_a + results_b
        
        return jsonify({
            "results": combined_results,
            "total": len(combined_results) # 近似总数
        })

    return jsonify({"results": [], "total": 0})        "lang": lang,
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
