# case_details.py
# pip install curl_cffi

from pathlib import Path
from datetime import datetime
import json
from curl_cffi import requests

URL = "https://clerkweb.summitoh.net/PublicSite/CaseDetail.aspx?CaseNo=CV-2024-08-3427&Suffix=&Type="

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "max-age=0",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    'Sec-CH-UA': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
    "Sec-CH-UA-Mobile": "?0",
    'Sec-CH-UA-Platform': '"Windows"',
}

COOKIES = {
    "__utmc": "257976024",
    "ASP.NET_SessionId": "2gbu40xaxpsm0j5xptyudu5d",
    "__utmz": "257976024.1754275924.3.2.utmccn=(referral)|utmcsr=chatgpt.com|utmcct=/|utmcmd=referral",
    "ASPSESSIONIDACVRSTBR": "DMJAHGPDHPPAHPPCMGLAPOMO",
    "ASPSESSIONIDAGRRSTBR": "EPKAHGPDOANPAKKAHFHAIDMO",
    "__utma": "257976024.371780669.1754268998.1754275924.1754278939.4",
    "ASPSESSIONIDCAUTQRCQ": "MADGKLKDIAFMBMDENCKJAEBA",
    "ASPSESSIONIDCEQTQRCQ": "CKEGKLKDGEJDBBMHLJOCAPNK",
}

def main():
    out = Path("out")
    out.mkdir(exist_ok=True)

    # NOTE: removed http2=True (unsupported). `impersonate="chrome"` already negotiates HTTP/2 when available.
    resp = requests.get(
        URL,
        headers=HEADERS,
        cookies=COOKIES,
        allow_redirects=True,
        timeout=60,
        impersonate="chrome",
    )

    # Save body (decoded if compressed)
    body_path = out / "response_body.html"
    body_path.write_bytes(resp.content)

    # Save metadata (status, headers, etc.)
    meta = {
        "fetched_at_utc": datetime.utcnow().isoformat() + "Z",
        "url": resp.url,
        "status_code": resp.status_code,
        "reason": getattr(resp, "reason", None),
        "response_headers": dict(resp.headers),
        "request_headers_sent": HEADERS,
        "cookies_sent": COOKIES,
    }
    (out / "response_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(f"Saved:\n- {body_path}\n- {out / 'response_meta.json'}")

if __name__ == "__main__":
    main()
