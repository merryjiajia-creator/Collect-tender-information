#!/usr/bin/env python3
"""一次性获取腾讯文档 refresh_token 的辅助脚本（OAuth 授权码模式）。

前置：在 https://docs.qq.com/open 注册应用，拿到 client_id / client_secret，
并配置回调地址（可用 http://localhost:8888/callback）。

用法：
    export TENCENT_CLIENT_ID=xxx
    export TENCENT_CLIENT_SECRET=xxx
    python scripts/get_refresh_token.py
按提示在浏览器完成授权，脚本会打印 refresh_token，填入 GitHub Secrets 即可。
"""
import os
import sys
import webbrowser
import http.server
import urllib.parse
import requests

CLIENT_ID = os.environ.get("TENCENT_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("TENCENT_CLIENT_SECRET", "")
REDIRECT = os.environ.get("TENCENT_REDIRECT_URI", "http://localhost:8888/callback")
SCOPE = "all"

AUTH_URL = "https://docs.qq.com/oauth/v2/authorize"
TOKEN_URL = "https://docs.qq.com/oauth/v2/token"

_code_holder = {}


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        q = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(q.query)
        if "code" in params:
            _code_holder["code"] = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("授权成功，可关闭本页面返回终端。".encode("utf-8"))
        else:
            self.send_response(400)
            self.end_headers()

    def log_message(self, *a):
        pass


def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        print("请先设置 TENCENT_CLIENT_ID 与 TENCENT_CLIENT_SECRET 环境变量")
        sys.exit(1)

    auth = (f"{AUTH_URL}?client_id={CLIENT_ID}&redirect_uri={urllib.parse.quote(REDIRECT)}"
            f"&response_type=code&scope={SCOPE}")
    print("请在浏览器完成授权：")
    print(auth)
    try:
        webbrowser.open(auth)
    except Exception:
        pass

    host, port = "localhost", int(urllib.parse.urlparse(REDIRECT).port or 8888)
    srv = http.server.HTTPServer((host, port), Handler)
    print(f"等待回调 {REDIRECT} ...")
    while "code" not in _code_holder:
        srv.handle_request()
    code = _code_holder["code"]

    resp = requests.get(TOKEN_URL, params={
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT,
    }, timeout=30)
    data = resp.json()
    print("\n===== Token 结果 =====")
    print(f"access_token : {data.get('access_token','')[:12]}...")
    print(f"user_id      : {data.get('user_id','')}")
    print(f"REFRESH_TOKEN（填入 GitHub Secrets TENCENT_REFRESH_TOKEN）：")
    print(data.get("refresh_token", ""))


if __name__ == "__main__":
    main()
