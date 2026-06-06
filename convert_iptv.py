#!/usr/bin/env python3
"""
iptv-org 中国频道 -> IPTV-API result.txt 格式转换脚本
每天自动从 iptv-org/iptv 拉取 cn.m3u，转成 #genre# 分类格式
"""

import os
import sys
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
            # 提取频道名（最后一个逗号后面的内容）
            if "," in line:
                current_name = line.split(",")[-1].strip()
            else:
                current_name = "Unknown"
        elif line and not line.startswith("#") and current_name:
            # 清理频道名
            clean_name = current_name.replace(" [Not 24/7]", "").strip()
            channels.append((clean_name, line))
            current_name = ""
    return channels


def categorize(channels: list) -> dict:
    """将频道分类"""
    categorized = {}
    assigned = set()

    # 先按规则分类
    for cat_name, keywords in CATEGORIES.items():
        cat_channels = []
        for name, url in channels:
            if any(kw.lower() in name.lower() for kw in keywords) and name not in assigned:
                cat_channels.append((name, url))
                assigned.add(name)
        categorized[cat_name] = cat_channels

    # 剩余未分类的放到"其他"
    remaining = [(n, u) for n, u in channels if n not in assigned]
    if remaining:
        categorized["📺其他频道"] = remaining

    return categorized


def write_result(categorized: dict, output_file: str):
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

    return len([c for ch in categorized.values() for c in ch])


def write_m3u(categorized: dict, output_file: str):
    """写入 result.m3u 格式"""
    with open(output_file, "w", encoding="utf-8") as f:
        f.write('#EXTM3U x-tvg-url="https://iptv-org.github.io/epg.xml"\n')

        for cat_name, channels in categorized.items():
            f.write(f"\n# Group: {cat_name}\n")
            for name, url in channels:
                # 尝试从名称提取 tvg-id
                tvg_id = name.split("(")[0].strip().replace(" ", "")
                f.write(f'#EXTINF:-1 tvg-name="{name}" tvg-id="{tvg_id}",{name}\n')
                f.write(f"{url}\n")


def main():
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
    total = write_result(categorized, OUTPUT_FILE)
    write_m3u(categorized, M3U_OUTPUT)

    # 统计每个分类的频道数
    print(f"\n✅ 转换完成! 共 {total} 个频道:")
    for cat, chs in categorized.items():
        print(f"  {cat}: {len(chs)}")

    print(f"\n输出文件:")
    print(f"  TXT: {OUTPUT_FILE}")
    print(f"  M3U: {M3U_OUTPUT}")


if __name__ == "__main__":
    main()
