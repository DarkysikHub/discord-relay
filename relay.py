#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт пересылки постов из чужих групп VK и Telegram каналов в Discord через Вебхуки
Требования:
    pip install requests beautifulsoup4

Запуск:
    python relay.py

Для работы в фоне на Linux/VPS:
    nohup python3 relay.py > relay.log 2>&1 &
"""

import os
import re
import json
import time
from datetime import datetime
import requests
from bs4 import BeautifulSoup

# Совместимость с JSON-литералами
true = True
false = False
null = None

STATE_FILE = "seen_posts.json"

CONFIG_RULES = [
  {
    "name": "Telegram: Новости технологий",
    "type": "telegram",
    "source": "telegram",
    "vk_token": "",
    "discord_webhook": "",
    "use_webhook_profile": True,
    "bot_name": "",
    "bot_avatar": "",
    "custom_emoji": "✈️",
    "title_template": "{emoji} Telegram: {title}",
    "content_template": "📢 **Новый пост из [{channel}](<{url}>)**",
    "show_author": True,
    "show_footer": True,
    "embed_color": "#24A1DE",
    "interval_sec": 120,
    "filter_keywords": [],
    "exclude_keywords": [],
    "include_link": True
  },
  {
    "name": "VK: Хабр (Без приложений и без токенов)",
    "type": "vk",
    "source": "habr",
    "vk_token": "",
    "discord_webhook": "",
    "use_webhook_profile": True,
    "bot_name": "",
    "bot_avatar": "",
    "custom_emoji": "🔵",
    "title_template": "{emoji} ВКонтакте: {title}",
    "content_template": "📢 **Новый пост из [{channel}](<{url}>)**",
    "show_author": True,
    "show_footer": True,
    "embed_color": "#4C75A3",
    "interval_sec": 180,
    "filter_keywords": [],
    "exclude_keywords": [],
    "include_link": True
  },
  {
    "name": "TG: https://t.me/basoy_channel",
    "type": "telegram",
    "source": "basoy_channel",
    "vk_token": "",
    "discord_webhook": "https://discord.com/api/webhooks/1550822342777774153/rlbyCcPgYqnHUBN4ccY3IpihRXSGsP6ilB6vZvx0rx6_Is9C51ShfJeqCTAugx1QrcNu",
    "use_webhook_profile": True,
    "bot_name": "",
    "bot_avatar": "",
    "custom_emoji": "✈️",
    "title_template": "{title}",
    "content_template": "<@&1550816885094752297>",
    "show_author": False,
    "show_footer": True,
    "embed_color": "#5865F2",
    "interval_sec": 60,
    "filter_keywords": [],
    "exclude_keywords": [],
    "include_link": True
  },
  {
    "name": "VK: https://vk.ru/rmroleplay",
    "type": "vk",
    "source": "rmroleplay",
    "vk_token": "",
    "discord_webhook": "https://discord.com/api/webhooks/1550822342777774153/rlbyCcPgYqnHUBN4ccY3IpihRXSGsP6ilB6vZvx0rx6_Is9C51ShfJeqCTAugx1QrcNu",
    "use_webhook_profile": True,
    "bot_name": "",
    "bot_avatar": "",
    "custom_emoji": "🔵",
    "title_template": "{title}",
    "content_template": "<@&1550816885094752297>",
    "show_author": False,
    "show_footer": True,
    "embed_color": "#5865F2",
    "interval_sec": 60,
    "filter_keywords": [],
    "exclude_keywords": [],
    "include_link": True
  }
]

def load_seen_posts():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception as e:
            print(f"Ошибка чтения {STATE_FILE}: {e}")
    return set()

def save_seen_posts(seen_set):
    try:
        data = list(seen_set)[-500:]
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка сохранения {STATE_FILE}: {e}")

seen_post_ids = load_seen_posts()

def clean_source(text):
    text = str(text or "").strip()
    text = re.sub(r"^https?://[^/]+/", "", text)
    text = text.lstrip("@").strip("/").split("/")[0].split("?")[0]
    return text

def fetch_telegram(channel_input):
    channel = clean_source(channel_input)
    url = f"https://t.me/s/{channel}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ru-RU,ru;q=0.9",
    }
    
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    title_el = soup.find("div", class_="tgme_channel_info_header_title")
    title = title_el.get_text(strip=True) if title_el else channel

    avatar_el = soup.find("img", class_="tgme_page_photo_image")
    avatar = avatar_el.get("src") if avatar_el else ""

    posts = []
    wraps = soup.find_all("div", class_="tgme_widget_message_wrap")

    for wrap in wraps:
        msg = wrap.find("div", class_="tgme_widget_message")
        if not msg:
            continue
        data_post = msg.get("data-post")
        if not data_post:
            continue

        text_el = msg.find("div", class_="tgme_widget_message_text")
        text = text_el.get_text(separator="\n", strip=True) if text_el else ""

        images = []
        photos = msg.find_all("a", class_="tgme_widget_message_photo_wrap")
        for p in photos:
            style = p.get("style", "")
            if "url(" in style:
                bg_url = style.split("url(")[1].split(")")[0].replace("'", "").replace('"', '').strip()
                if bg_url and bg_url not in images:
                    images.append(bg_url)

        time_el = msg.find("time")
        dt_str = time_el.get("datetime") if time_el else None

        if text or images:
            posts.append({
                "id": data_post,
                "title": title,
                "avatar": avatar,
                "text": text,
                "images": images,
                "url": f"https://t.me/{data_post}",
                "iso_time": dt_str or datetime.utcnow().isoformat()
            })

    return posts

def fetch_vk(source_input, vk_token):
    cleaned = clean_source(source_input)
    
    # 1. Если задан токен, используем wall.get
    if vk_token and vk_token.strip():
        try:
            params = {
                "v": "5.199",
                "access_token": vk_token.strip(),
                "count": 10,
                "extended": 1,
            }
            if re.match(r"^\d+$", cleaned):
                params["owner_id"] = f"-{cleaned}"
            else:
                params["domain"] = cleaned

            resp = requests.get("https://api.vk.com/method/wall.get", params=params, timeout=10)
            data = resp.json()
            if "error" not in data:
                response = data.get("response", {})
                groups = response.get("groups", [])
                group_name = groups[0].get("name", cleaned) if groups else cleaned
                group_avatar = groups[0].get("photo_200", "") if groups else ""

                posts = []
                for item in response.get("items", []):
                    post_id = f"vk_{item['owner_id']}_{item['id']}"
                    post_url = f"https://vk.com/wall{item['owner_id']}_{item['id']}"
                    text = item.get("text", "")

                    images = []
                    for att in item.get("attachments", []):
                        if att.get("type") == "photo" and "photo" in att:
                            sizes = att["photo"].get("sizes", [])
                            if sizes:
                                images.append(sizes[-1]["url"])

                    dt = datetime.utcfromtimestamp(item.get("date", time.time()))
                    posts.append({
                        "id": post_id,
                        "title": group_name,
                        "avatar": group_avatar,
                        "text": text,
                        "images": images,
                        "url": post_url,
                        "iso_time": dt.isoformat() + "Z"
                    })
                return posts
        except Exception:
            pass

    # 2. Парсер публичного виджета ВКонтакте (без токена и без приложений)
    numeric_gid = ""
    if re.match(r"^\d+$", cleaned):
        numeric_gid = cleaned
    elif re.match(r"^-\d+$", cleaned):
        numeric_gid = cleaned.lstrip("-")
    elif re.match(r"^(public|club)\d+$", cleaned, re.IGNORECASE):
        numeric_gid = re.sub(r"^(public|club)", "", cleaned, flags=re.IGNORECASE)
    else:
        page_resp = requests.get(f"https://vk.com/{cleaned}", headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        m = re.search(r'"owner_id":\s*(-?\d+)', page_resp.text)
        if m:
            numeric_gid = m.group(1).lstrip("-")
        else:
            m2 = re.search(r'(?:public|club|group_id|gid)["\s:=_-]+(\d{4,12})', page_resp.text, re.IGNORECASE)
            if m2:
                numeric_gid = m2.group(1)

    if not numeric_gid:
        raise RuntimeError(f"Не удалось определить числовой ID группы для {cleaned}")

    w_url = f"https://vk.com/widget_community.php?app=0&width=auto&_ver=1&gid={numeric_gid}&mode=4"
    w_resp = requests.get(w_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
    w_resp.encoding = "windows-1251"

    soup = BeautifulSoup(w_resp.text, "html.parser")
    title_el = soup.find("a", class_="wcommunity_name") or soup.find(class_="community_head")
    group_name = title_el.get_text(strip=True) if title_el else cleaned

    avatar_el = soup.select_one(".wcommunity_avatar img")
    group_avatar = avatar_el.get("src") if avatar_el else ""

    posts = []
    for el in soup.find_all(class_="wall_post_cont"):
        raw_id = el.get("id", "")
        m = re.search(r"wpt(-?\d+)_(\d+)", raw_id)
        owner_id = m.group(1) if m else f"-{numeric_gid}"
        item_id = m.group(2) if m else str(int(time.time()))
        post_id = f"vk_{owner_id}_{item_id}"
        post_url = f"https://vk.com/wall{owner_id}_{item_id}"

        text_el = el.find(class_="wall_post_text")
        text = text_el.get_text(separator="\n", strip=True) if text_el else ""

        images = []
        for img in el.find_all("img"):
            src = img.get("src", "")
            if src and "avatar" not in src and src not in images:
                images.append(src)

        for div in el.find_all(style=re.compile(r"background-image")):
            st = div.get("style", "")
            if "url(" in st:
                bg_url = st.split("url(")[1].split(")")[0].replace("'", "").replace('"', '').strip()
                if bg_url and bg_url not in images:
                    images.append(bg_url)

        if text or images:
            posts.append({
                "id": post_id,
                "title": group_name,
                "avatar": group_avatar,
                "text": text,
                "images": images,
                "url": post_url,
                "iso_time": datetime.utcnow().isoformat() + "Z"
            })

    return posts

def send_to_discord(webhook_url, post, rule):
    desc = post["text"] if post["text"] else "*(Вложение)*"
    if len(desc) > 3900:
        desc = desc[:3900] + "...\n\n*(текст сокращен)*"

    hex_str = rule.get("embed_color", "#5865F2").replace("#", "")
    color = int(hex_str, 16) if hex_str else 0x5865F2
    emoji = rule.get("custom_emoji") or ("🔵" if rule["type"] == "vk" else "✈️")

    title_tmpl = rule.get("title_template")
    if title_tmpl and title_tmpl.strip():
        embed_title = (
            title_tmpl.replace("{emoji}", emoji)
            .replace("{source}", "ВКонтакте" if rule["type"] == "vk" else "Telegram")
            .replace("{title}", post["title"])
            .replace("{channel}", post["title"])
            .replace("{author}", post["title"])
        )
    else:
        embed_title = f"{emoji} {'ВКонтакте' if rule['type'] == 'vk' else 'Telegram'}: {post['title']}"

    embed = {
        "title": embed_title,
        "url": post["url"],
        "description": desc,
        "color": color,
        "timestamp": post["iso_time"],
    }

    if rule.get("show_author", True) and post.get("avatar"):
        embed["author"] = {
            "name": post["title"],
            "url": post["url"],
            "icon_url": post["avatar"]
        }

    if rule.get("show_footer", True):
        embed["footer"] = {
            "text": "VK Wall Relay" if rule["type"] == "vk" else "Telegram Channel Relay",
            "icon_url": "https://vk.com/images/svg_icons/ic_head_logo.svg" if rule["type"] == "vk" else "https://telegram.org/img/t_logo.png"
        }

    if post.get("images"):
        embed["image"] = {"url": post["images"][0]}

    payload = {
        "embeds": [embed]
    }

    use_native = rule.get("use_webhook_profile", True) and not (rule.get("bot_name") or "").strip()
    if not use_native:
        if rule.get("bot_name", "").strip():
            payload["username"] = rule["bot_name"].strip()
        if rule.get("bot_avatar", "").strip():
            payload["avatar_url"] = rule["bot_avatar"].strip()

    if rule.get("include_link", True):
        content_tmpl = rule.get("content_template")
        if content_tmpl and content_tmpl.strip():
            payload["content"] = (
                content_tmpl.replace("{emoji}", emoji)
                .replace("{source}", "ВКонтакте" if rule["type"] == "vk" else "Telegram")
                .replace("{channel}", post["title"])
                .replace("{author}", post["title"])
                .replace("{url}", post["url"])
            )
        else:
            payload["content"] = f"{emoji} **Новый пост из [{post['title']}](<{post['url']}>)**"

    res = requests.post(webhook_url, json=payload, timeout=10)
    res.raise_for_status()

def check_rule(rule):
    webhook = rule.get("discord_webhook")
    if not webhook:
        return

    try:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Проверка {rule['type']}: {rule['source']}...")
        posts = fetch_vk(rule["source"], rule.get("vk_token")) if rule["type"] == "vk" else fetch_telegram(rule["source"])
        
        posts = list(reversed(posts))

        for post in posts:
            p_id = post["id"]
            if p_id in seen_post_ids:
                continue

            lower_text = post["text"].lower()
            inc = rule.get("filter_keywords", [])
            exc = rule.get("exclude_keywords", [])

            if inc and not any(k.lower() in lower_text for k in inc):
                seen_post_ids.add(p_id)
                continue
            if exc and any(k.lower() in lower_text for k in exc):
                seen_post_ids.add(p_id)
                continue

            print(f"[+] Отправка поста {p_id} в Discord...")
            send_to_discord(webhook, post, rule)
            seen_post_ids.add(p_id)
            save_seen_posts(seen_post_ids)
            time.sleep(1)

    except Exception as e:
        print(f"[ERROR {rule['name']}]: {e}")

def main():
    print("=== Запуск Python Relay: VK & Telegram -> Discord ===")
    
    port_str = os.environ.get("PORT")
    if port_str:
        import threading
        from http.server import HTTPServer, BaseHTTPRequestHandler
        
        class HealthCheckHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"status":"ok","service":"python-discord-relay"}')
            def log_message(self, format, *args):
                return
                
        try:
            http_port = int(port_str)
            server = HTTPServer(('0.0.0.0', http_port), HealthCheckHandler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            print(f"[HTTP] Health-check сервер активен на порту {http_port}")
        except Exception as err:
            print(f"[HTTP Error]: {err}")

    import sys
    is_once = "--once" in sys.argv

    while True:
        for rule in CONFIG_RULES:
            env_hook = os.environ.get("DISCORD_WEBHOOK")
            if env_hook:
                rule["discord_webhook"] = env_hook
            check_rule(rule)
            time.sleep(2)

        if is_once:
            print("[OK] Однократная проверка завершена (--once). Выход.")
            break

        time.sleep(60)

if __name__ == "__main__":
    main()
