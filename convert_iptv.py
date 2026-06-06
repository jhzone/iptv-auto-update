#!/usr/bin/env python3
"""
IPTV 自动更新脚本
每天自动从 iptv-org/iptv 和 iptv.mzone.dpdns.org/abc123 拉取频道，
转成 IPTV-API result.txt 格式
"""

import os
import sys
import re
import http.client
from datetime import datetime
from urllib.parse import unquote

# ==================== 配置区 ====================
OUTPUT_DIR = os.environ.get("IPTV_OUTPUT_DIR", "output")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "result.txt")
M3U_OUTPUT = os.path.join(OUTPUT_DIR, "result.m3u")
IPTV_ORG_URL = "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/cn.m3u"

# 频道分类规则（关键词匹配）
CATEGORIES = {
    "📺央视频道": ["CCTV", "CCTV-"],
    "💰央视付费频道": [
        "风云", "第一剧场", "怀旧剧场", "女性时尚", "央视台球",
        "高尔夫网球", "风云足球", "风云音乐", "电视指南",
        "世界地理", "兵器科技", "文化精品", "求索",
        "发现之旅", "家庭理财", "精品", "高尔夫", "网球",
    ],
    "📡卫视频道": [
        "卫视", "TVS", "TVB", "翡翠", "明珠",
    ],
    "🌊港·澳·台": [
        "香港", "台湾", "澳门", "凤凰", "卫视中文",
        "東森", "民視", "台視", "公視", "大爱", "公共",
        "客家", "人间", "大爱", "佛光", "圆山",
        "中天", "年代", "TVBS", "TVMI", "东森",
    ],
    "🎥咪咕直播": ["咪咕"],
}


def download_m3u(url: str) -> str:
    """下载 m3u 文件"""
    parsed = url.split("/")
    domain = parsed[2]
    path = "/" + "/".join(parsed[3:])

    conn = http.client.HTTPConnection(domain, timeout=30)
    conn.request("GET", path)
    resp = conn.getresponse()

    if resp.status in (301, 302, 307, 308):
        location = resp.getheader("Location")
        rdomain = location.split("/")[2]
        rpath = "/" + "/".join(location.split("/")[3:])
        if location.startswith("https"):
            conn2 = http.client.HTTPSConnection(rdomain, timeout=30)
        else:
            conn2 = http.client.HTTPConnection(rdomain, timeout=30)
        conn2.request("GET", rpath)
        resp2 = conn2.getresponse()
        body = resp2.read()
        conn2.close()
    else:
        body = resp.read()
    conn.close()

    return body.decode("utf-8", errors="ignore")


def parse_m3u(text: str) -> list:
    """解析 m3u 文件，返回 (频道名, URL) 列表"""
    channels = []
    current_name = ""
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("#EXTINF"):
            if "," in line:
                current_name = line.split(",")[-1].strip()
            else:
                current_name = "Unknown"
        elif line and not line.startswith("#") and current_name:
            clean_name = current_name.replace(" [Not 24/7]", "").strip()
            channels.append((clean_name, line))
            current_name = ""
    return channels


def categorize(channels: list) -> dict:
    """将频道按规则分类"""
    categorized = {}
    assigned = set()

    for cat_name, keywords in CATEGORIES.items():
        cat_channels = []
        for name, url in channels:
            if any(kw.lower() in name.lower() for kw in keywords) and name not in assigned:
                cat_channels.append((name, url))
                assigned.add(name)
        categorized[cat_name] = cat_channels

    remaining = [(n, u) for n, u in channels if n not in assigned]
    if remaining:
        categorized["📺其他频道"] = remaining

    return categorized


def fetch_abc123() -> dict:
    """从 abc123 拉取 M3U 数据，转成 {分类: [(频道名, URL)]}"""
    url = "https://iptv.mzone.dpdns.org/abc123"

    parsed = url.split("/")
    domain = parsed[2]
    path = "/" + "/".join(parsed[3:])

    conn = http.client.HTTPConnection(domain, timeout=60)
    conn.request("GET", path, headers={"User-Agent": "Mozilla/5.0"})
    resp = conn.getresponse()
    body = resp.read()
    conn.close()

    text = body.decode("utf-8", errors="ignore")
    lines = text.strip().split("\n")

    channels = {}
    current_group = "其他"
    for i, line in enumerate(lines):
        line = line.strip()
        if line.startswith("#EXTINF"):
            g = re.search(r'group-title="([^"]*)"', line)
            n = re.search(r',([^,]+)$', line)
            if g:
                current_group = g.group(1)
            if n:
                name = n.group(1).strip()
                if name:
                    if current_group not in channels:
                        channels[current_group] = []
                    if i + 1 < len(lines):
                        url_next = lines[i + 1].strip()
                        channels[current_group].append((name, url_next))
    return channels


def write_result(categorized: dict, output_file: str, abc_channels: dict = None):
    """写入 result.txt 格式"""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("# 更新时间,#genre#\n")
        f.write(f"{now},https://iptv.catvod.com/catvod?id=CCTV1%E7%BB%BC%E5%90%88&line=1\n")
        f.write("\n")

        for cat_name, channels in categorized.items():
            f.write(f"{cat_name},#genre#\n")
            for name, url in channels:
                f.write(f"{name},{url}\n")
            f.write("\n")

        # 追加 abc123 数据
        if abc_channels:
            f.write("# === IPTV.MZONE.DPDNS.ORG/ABC123 SOURCE ===\n")
            for cat_name, channels in abc_channels.items():
                f.write(f"{cat_name},#genre#\n")
                for name, url in channels:
                    f.write(f"{name},{url}\n")
                f.write("\n")

    total = len([c for ch in categorized.values() for c in ch])
    if abc_channels:
        total += len([c for ch in abc_channels.values() for c in ch])
    return total


def write_m3u(categorized: dict, output_file: str):
    """写入 result.m3u 格式"""
    with open(output_file, "w", encoding="utf-8") as f:
        f.write('#EXTM3U x-tvg-url="https://iptv-org.github.io/epg.xml"\n')

        for cat_name, channels in categorized.items():
            f.write(f"\n# Group: {cat_name}\n")
            for name, url in channels:
                tvg_id = name.split("(")[0].strip().replace(" ", "")
                f.write(f'#EXTINF:-1 tvg-name="{name}" tvg-id="{tvg_id}",{name}\n')
                f.write(f"{url}\n")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 1. 拉取 iptv-org
    print(f"[{datetime.utcnow().isoformat()}] 开始下载 iptv-org cn.m3u...")
    try:
        m3u_text = download_m3u(IPTV_ORG_URL)
    except Exception as e:
        print(f"❌ 下载失败: {e}")
        sys.exit(1)

    channels = parse_m3u(m3u_text)
    print(f"✓ 解析到 {len(channels)} 个频道")

    if not channels:
        print("❌ 未解析到任何频道")
        sys.exit(1)

    categorized = categorize(channels)

    # 2. 拉取 abc123
    print(f"\n[{datetime.utcnow().isoformat()}] 开始下载 abc123...")
    try:
        abc_channels = fetch_abc123()
        abc_total = sum(len(chs) for chs in abc_channels.values())
        print(f"✓ abc123 解析到 {abc_total} 个频道")
    except Exception as e:
        print(f"❌ abc123 下载失败: {e}")
        abc_channels = None
        abc_total = 0

    # 3. 写入结果
    total = write_result(categorized, OUTPUT_FILE, abc_channels)
    write_m3u(categorized, M3U_OUTPUT)

    # 4. 统计
    print(f"\n✅ 转换完成! 共 {total} 个频道:")
    for cat, chs in categorized.items():
        print(f"  {cat}: {len(chs)}")
    if abc_channels and abc_total > 0:
        print(f"\n📺 abc123 源 ({abc_total} 个):")
        for cat, chs in abc_channels.items():
            if chs:
                print(f"  {cat}: {len(chs)}")

    print(f"\n输出文件:")
    print(f"  TXT: {OUTPUT_FILE}")
    print(f"  M3U: {M3U_OUTPUT}")


if __name__ == "__main__":
    main()
