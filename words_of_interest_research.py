# 必要なライブラリ
import requests
import time
from bs4 import BeautifulSoup
from notion_client import Client
import urllib.parse

# ========= 設定 =========
NOTION_TOKEN = "xxx"
DATABASE_ID = "xxx"
GROQ_API_KEY = "xxx"
HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

# ========= Notion関連 =========
def get_unprocessed_keywords():
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    payload = {
        "filter": {
            "property": "状態",
            "select": {
                "equals": "未処理"
            }
        }
    }
    response = requests.post(url, headers=HEADERS, json=payload)
    response.raise_for_status()
    results = response.json().get("results", [])
    return [(r["id"], r["properties"]["ワード"]["title"][0]["text"]["content"]) for r in results]

def update_notion_page(page_id, summary):
    # ブロック構築
    block_payload = {
        "children": [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": summary
                            }
                        }
                    ]
                }
            }
        ]
    }
    block_url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    res = requests.patch(block_url, headers=HEADERS, json=block_payload)
    res.raise_for_status()

    # 状態を更新
    page_url = f"https://api.notion.com/v1/pages/{page_id}"
    payload = {
        "properties": {
            "状態": {
                "select": {"name": "要約済み"}
            }
        }
    }
    requests.patch(page_url, headers=HEADERS, json=payload)

# ========= DuckDuckGo検索 =========
def duckduckgo_search(query):
    url = f"https://html.duckduckgo.com/html/?q={query}とは"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")
    links = [a['href'] for a in soup.select("a.result__a")][:3]  # 上位3件
    return links

# ========= Web本文抽出 =========
def extract_main_text(url):
    try:
        # DuckDuckGo リダイレクトの処理
        if url.startswith('//duckduckgo.com/l/?uddg='):
            parsed = urllib.parse.urlparse(url)
            query = urllib.parse.parse_qs(parsed.query)
            real_url = query.get('uddg', [None])[0]
            if real_url:
                url = urllib.parse.unquote(real_url)
        res = requests.get(url, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        paragraphs = soup.find_all('p')
        text = "\n".join(p.get_text() for p in paragraphs)
        return text[:2000]  # トークン制限対策
    except:
        return ""

# ========= Groq要約 =========
def summarize_with_groq(word, text):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": f"""次の文章は、{word}という言葉の説明文です。
             これを子どもやお年寄りにも分かりやすく、箇条書きで、２００文字程度で、次の形式で出力してください。  
             ・これは何か（改行して本文開始）
             ・なぜそれが必要か（改行して本文開始）
             ・どのように実現するか（改行して本文開始）
             ・理解を深めるための補足情報（改行して本文開始）
             ・関連ワード"""},
            {"role": "user", "content": text}
        ],
        "temperature": 0.7
    }
    res = requests.post(url, headers=headers, json=data)
    res.raise_for_status()
    return res.json()["choices"][0]["message"]["content"]

# ========= 実行ロジック =========
def main():
    keywords = get_unprocessed_keywords()
    for page_id, word in keywords:
        print(f"\n処理中: {word}")
        urls = duckduckgo_search(word)
        all_text = "\n".join([extract_main_text(url) for url in urls if url])
        if not all_text:
            print("→ 本文取得失敗")
            continue
        summary = summarize_with_groq(word, all_text)
        update_notion_page(page_id, summary)
        print("→ 要約完了")
        time.sleep(1)  # Notion API制限対策

if __name__ == "__main__":
    main()
