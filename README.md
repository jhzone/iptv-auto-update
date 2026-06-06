# IPTV 自动更新

每天 08:00（北京时间）自动从 [iptv-org/iptv](https://github.com/iptv-org/iptv) 拉取中国频道，转换成 IPTV-API 格式。

## 文件说明

- `convert_iptv.py` — 核心转换脚本
- `.github/workflows/iptv-daily.yml` — GitHub Actions 定时任务

## 输出格式

### result.txt (IPTV-API 格式)
```
📺央视频道,#genre#
CCTV-1,http://xxx
CCTV-2,http://yyy

📡卫视频道,#genre#
湖南卫视,http://xxx
...
```

### result.m3u (标准 m3u)
```
#EXTM3U x-tvg-url="https://iptv-org.github.io/epg.xml"
#EXTINF:-1 tvg-name="CCTV-1",CCTV-1
http://xxx
```

## 本地使用

```bash
# 直接运行
python3 convert_iptv.py

# 自定义输出目录
export IPTV_OUTPUT_DIR=/path/to/output
python3 convert_iptv.py
```

## 频道分类

- 📺 央视频道 — CCTV-1 ~ CCTV-17
- 💰 央视付费频道 — 风云系列、剧场系列等
- 📡 卫视频道 — 全国卫视
- 🌊 港·澳·台 — 凤凰、台湾频道等
- 📺 其他频道 — 地方台、教育台、CGTN 等
