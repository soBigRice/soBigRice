#!/usr/bin/env python3
"""Refresh public profile metadata and README tables; never commit or publish."""

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
import html
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
EN_COPY = json.loads((ROOT / "scripts/profile_copy.en.json").read_text())
CATEGORIES = {
    "soBigRice": "个人主页", "soRound_os": "嵌入式系统", "port-guardian": "桌面工具",
    "three_shader_example": "图形实验", "ohBangs": "桌面交互", "oh-fans": "桌面工具",
    "-API-": "服务端", "lsky_v2.1_node_server": "服务端", "snapshot": "游戏实验",
    "WebGL_heart_beat": "图形实验", "wifiCalendar": "嵌入式设备", "graphical.top": "图形内容",
    "github_action_server": "开发工具", "Hello-WebGPU": "图形实验", "NodeMessage": "服务端",
    "Cesium.path": "图形组件", "fpsActor": "游戏实验", "old_github_io": "工具集合",
    "ar_view": "AR 实验", "npm-library-universal-template": "开发模板",
    "guigui267.github.io": "早期主页", "3Ddemo": "图形组件", "Graduation-project-WebXR": "XR 实验",
}


def api(endpoint, paginate=False):
    command = ["gh", "api", endpoint]
    if paginate:
        command += ["--paginate", "--slurp"]
    result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=90)
    value = json.loads(result.stdout)
    return [item for page in value for item in page] if paginate else value


def public_releases(releases):
    # Authenticated GitHub API responses can include drafts in an owned repo.
    public = [{
        "tag": r["tag_name"], "url": r["html_url"], "prerelease": r["prerelease"],
        "published_at": r["published_at"],
        "downloads": sum(a["download_count"] for a in r.get("assets", [])),
    } for r in releases if not r["draft"] and r["published_at"]]
    return sorted(public, key=lambda release: release["published_at"], reverse=True)


def summarize(data):
    repos = data["repositories"]
    if any(r.get("private") or r.get("visibility", "public") != "public" for r in repos):
        raise ValueError("Refusing non-public repository data")
    original = [r for r in repos if not r["fork"]]
    languages, coverage = Counter(), Counter()
    for repo in original:
        languages.update(repo["languages"])
        coverage.update(repo["languages"].keys())
    return {
        "public_repos": len(repos), "original_repos": len(original), "fork_repos": len(repos)-len(original),
        "stars": sum(r["stars"] for r in repos), "forks_received": sum(r["forks"] for r in repos),
        "release_count": sum(len(r["releases"]) for r in repos),
        "downloads": sum(v["downloads"] for r in repos for v in r["releases"]),
        "languages": dict(languages.most_common()), "language_repos": dict(coverage),
    }


def collect(username, snapshot_date):
    user = api(f"users/{username}")
    repos = api(f"users/{username}/repos?type=owner&sort=pushed&per_page=100", paginate=True)
    if any(r["private"] or r.get("visibility") != "public" for r in repos):
        raise ValueError("Public endpoint returned non-public data")
    if len(repos) != user["public_repos"]:
        raise ValueError("Repository list changed during collection; refresh again")

    def enrich(repo):
        path = f"repos/{username}/{repo['name']}"
        languages = api(path + "/languages")
        releases = public_releases(api(path + "/releases?per_page=100", paginate=True))
        license_id = (repo.get("license") or {}).get("spdx_id")
        return {
            "name": repo["name"], "url": repo["html_url"], "description": repo["description"] or "",
            "homepage": repo["homepage"] or "", "fork": repo["fork"], "archived": repo["archived"],
            "private": False, "visibility": "public", "pushed_at": repo["pushed_at"],
            "primary_language": repo["language"], "languages": languages,
            "stars": repo["stargazers_count"], "forks": repo["forks_count"],
            "open_issues_and_prs": repo["open_issues_count"], "size_kib": repo["size"],
            "license": license_id if license_id and license_id != "NOASSERTION" else None,
            "releases": releases,
        }

    with ThreadPoolExecutor(max_workers=4) as pool:
        repositories = list(pool.map(enrich, repos))
    data = {
        "schema_version": 1, "snapshot_date": snapshot_date,
        "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "user": {k: user[k] for k in ("login", "name", "html_url", "created_at", "public_repos",
                                      "public_gists", "followers", "following")},
        "repositories": repositories,
    }
    data["summary"] = summarize(data)
    return data


def cell(value):
    # Source descriptions must not introduce Markdown columns or HTML controls.
    return html.escape(str(value)).replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def link(label, url):
    if not url.startswith(("https://", "http://")):
        raise ValueError("Unsupported public link")
    return f"[{cell(label)}]({quote(url, safe=':/?=&%#@+.-_~')})"


def table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |",
                       *["| " + " | ".join(row) + " |" for row in rows]])


def pushed_day(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone(timedelta(hours=8))).date().isoformat()


def localized(value, locale):
    if locale not in ("zh", "en"):
        raise ValueError(f"Unsupported profile language: {locale}")
    return EN_COPY["labels"].get(value, value) if locale == "en" else value


def description(value, locale):
    # Match the source copy, so an upstream edit cannot retain a stale translation.
    return EN_COPY["descriptions"].get(value, value) if locale == "en" else value


def blocks(data, locale="zh"):
    def text(value):
        return localized(value, locale)

    user, summary, repos = data["user"], data["summary"], data["repositories"]
    account = table(list(map(text, ["指标", "数据", "范围"])), [
        [text("公开仓库"), str(summary["public_repos"]), f"{text('原创')} {summary['original_repos']} / Fork {summary['fork_repos']}"],
        [text("获得的 Stars / Forks"), f"{summary['stars']} / {summary['forks_received']}", text("本人名下全部公开仓库，含适配 Fork")],
        [text("关注者 / 正在关注"), f"{user['followers']} / {user['following']}", text("GitHub 公开账号数据")],
        [text("公开 Gists"), str(user["public_gists"]), text("公开代码片段")],
        [text("加入 GitHub"), user["created_at"][:10], text("账号创建日期")],
        [text("原创仓库语言种类"), str(len(summary["languages"])), text("GitHub Linguist 检测结果，排除 Fork")],
        [text("公开 Releases"), str(summary["release_count"]), text("含预发布，排除草稿")],
        [text("Release 附件下载"), f"{summary['downloads']:,}", text("仅 GitHub 下载次数，不含 OTA / 镜像 / npm")],
    ])
    total = sum(summary["languages"].values())
    language = table(list(map(text, ["语言", "代码字节", "占比", "涉及原创仓库"])), [
        [cell(name), f"{count:,}", f"{count / total * 100:.2f}%", str(summary["language_repos"][name])]
        for name, count in summary["languages"].items()
    ])
    catalog = {}
    for fork, key in ((False, "original"), (True, "forks")):
        rows = []
        for r in repos:
            if r["fork"] != fork:
                continue
            language_name = " / ".join(sorted(r["languages"], key=r["languages"].get, reverse=True)[:3]) or text("未识别")
            kind = text("领克适配" if r["name"] == "LynkCo-DiPlay" else ("Fork" if fork else CATEGORIES.get(r["name"], "其他")))
            entry = [link(text("源码"), r["url"])]
            if r["homepage"] and r["homepage"].startswith(("https://", "http://")):
                entry.append(link(text("访问"), r["homepage"]))
            if r["releases"]:
                entry.append(link(text("发布"), r["url"] + "/releases"))
            rows.append([link(r["name"], r["url"]), f"**{kind}**<br>{cell(description(r['description'] or '—', locale))}",
                         cell(language_name), f"★ {r['stars']}<br>⑂ {r['forks']}<br>Open {r['open_issues_and_prs']}",
                         pushed_day(r["pushed_at"]), cell(r["license"] or text("未识别")), " · ".join(entry)])
        catalog[key] = table(list(map(text, ["项目", "方向与说明", "主要语言", "数据", "最近推送", "许可", "入口"])), rows)
    releases = []
    for r in repos:
        if not r["releases"]:
            continue
        stable = next((x for x in r["releases"] if not x["prerelease"]), None)
        latest = r["releases"][0]
        releases.append([link(r["name"], r["url"]), link(stable["tag"], stable["url"]) if stable else "—",
                         link(latest["tag"], latest["url"]) + (text(" · 预发布") if latest["prerelease"] else ""),
                         str(len(r["releases"])), f"{sum(x['downloads'] for x in r['releases']):,}",
                         pushed_day(latest["published_at"])])
    return {"account": account, "languages": language, **catalog,
            "releases": table(list(map(text, ["项目", "最近正式版", "最近发布", "Release 数", "附件总下载", "最近发布日期"])), releases),
            "snapshot": text("数据快照：**{date}** · 仅公开资料 · 日期按 UTC+8。图表与表格的统计范围分别在下方注明。").format(date=data["snapshot_date"])}


def dashboard(data, dark):
    summary, user = data["summary"], data["user"]
    bg, ink, muted, edge = ("#111018", "#f0eff8", "#9297b0", "#30263f") if dark else ("#f4f7fb", "#152137", "#66738a", "#dbe3ef")
    red, cyan = ("#ff537c", "#48ead3") if dark else ("#b51a48", "#007f82")
    metrics = [("PUBLIC REPOS", summary["public_repos"], red), ("ORIGINAL PROJECTS", summary["original_repos"], cyan),
               ("FORKS + ADAPTATIONS", summary["fork_repos"], red), ("STARS EARNED", summary["stars"], cyan),
               ("FORKS RECEIVED", summary["forks_received"], cyan), ("FOLLOWERS", user["followers"], red),
               ("LANGUAGES / ORIGINAL", len(summary["languages"]), cyan), ("RELEASE DOWNLOADS", f"{summary['downloads']:,}", red)]
    parts = []
    for i, (label, value, color) in enumerate(metrics):
        x, y = 35 + i % 4 * 312, 120 + i // 4 * 153
        parts.append(f'<text x="{x}" y="{y}" font-size="17" fill="{muted}" letter-spacing="1.5">{label}</text>'
                     f'<text x="{x}" y="{y+69}" font-size="61" fill="{ink}" font-weight="700">{value}</text>'
                     f'<path d="M{x} {y+96}h245" stroke="{edge}"/><path class="pulse" d="M{x} {y+96}h45" stroke="{color}" stroke-width="3"/>')
    description = "；".join(f"{label}: {value}" for label, value, _ in metrics)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="430" viewBox="0 0 1280 430" role="img" aria-labelledby="title desc">
<title id="title">soBigRice 公开开源数据</title><desc id="desc">{description}。快照 {data['snapshot_date']}。</desc>
<defs><linearGradient id="signal"><stop stop-color="{red}"/><stop offset="1" stop-color="{cyan}"/></linearGradient></defs>
<style>.pulse{{animation:signal 4s ease-in-out infinite}}@keyframes signal{{0%,100%{{stroke-opacity:.45}}50%{{stroke-opacity:1}}}}@media(prefers-reduced-motion:reduce){{.pulse{{animation:none}}}}</style>
<rect x="1" y="1" width="1278" height="428" rx="12" fill="{bg}" stroke="{edge}"/>
<path d="M25 1h1230" stroke="url(#signal)" stroke-width="3"/>
<g font-family="Arial,Helvetica,sans-serif"><text x="35" y="51" font-size="23" fill="{ink}" letter-spacing="3">PUBLIC SIGNALS</text>
<text x="1245" y="51" font-size="17" fill="{muted}" text-anchor="end">GITHUB API / {data['snapshot_date']}</text>
<path d="M35 74h1210" stroke="{edge}"/>{''.join(parts)}
<text x="35" y="405" font-size="16" fill="{muted}" letter-spacing="1">REAL PROJECTS. PUBLIC DATA. ONE CURIOUS DEVELOPER.</text></g></svg>'''


def render(data):
    # Validate every generated section before changing any local output.
    data["summary"] = summarize(data)
    outputs = {ROOT / "assets/profile-data.json": json.dumps(data, ensure_ascii=False, indent=2) + "\n"}
    for filename, locale in (("README.md", "zh"), ("README.en.md", "en")):
        readme = (ROOT / filename).read_text()
        for name, value in blocks(data, locale).items():
            pattern = rf"(<!-- PROFILE:{name}:START -->).*?(<!-- PROFILE:{name}:END -->)"
            readme, count = re.subn(pattern, lambda m: m[1] + "\n" + value + "\n" + m[2], readme, flags=re.S)
            if count != 1:
                raise ValueError(f"Expected one {filename} block: {name}")
        outputs[ROOT / filename] = readme
    for theme in ("dark", "light"):
        outputs[ROOT / f"assets/profile-signals-{theme}.svg"] = dashboard(data, theme == "dark")
    for path, content in outputs.items():
        path.write_text(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", default="soBigRice")
    parser.add_argument("--snapshot-date", default=datetime.now(timezone(timedelta(hours=8))).date().isoformat())
    parser.add_argument("--from-snapshot", type=Path, help="Render saved public data without networking")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9-]+", args.username):
        parser.error("Invalid GitHub username")
    date.fromisoformat(args.snapshot_date)
    data = json.loads(args.from_snapshot.read_text()) if args.from_snapshot else collect(args.username, args.snapshot_date)
    render(data)
    print(f"Updated {len(data['repositories'])} public repositories; local files only, no commit or push.")
    pending = [r["name"] for r in data["repositories"]
               if re.search(r"[\u4e00-\u9fff]", description(r["description"], "en"))]
    if pending:
        print("English descriptions need review: " + ", ".join(pending))


if __name__ == "__main__":
    main()
