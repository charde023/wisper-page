#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""publish_report.py — MD 보고서 1개를 GitHub Pages(charde023/page)에 발행한다.

`publish_report.ps1`의 맥(darwin, pwsh 없음) 크로스플랫폼 이식본. 로직 1:1 동일.
원본 `.ps1`은 시그마(윈도) 폴백으로 보존한다(맥-로컬-전사 구현계획서 롤백 원칙과 동일 철학).

동작:
  1. 입력 검증
  2. report.md → page/reports/{type}/{slug}/report.md 복사
  3. _template/make_report_html.py → index.html
  4. update_reports_index.py → 전체 인덱스 재생성
  5. git add reports/ → commit → pull --rebase → push
  6. 라이브 URL 출력

사용(맥):
  python workflow/publish_report.py \
      --report "/Users/charde023/workspace/obsidian/charde_n/APOM/보고서/주간보고/2026-W23.md" \
      --type weekly --slug 2026-W23 \
      --page-repo /Users/charde023/workspace/page

부분 실행(검증·안전):
  --no-push   commit 까지만(원격 push 안 함)
  --no-git    파일 생성(html+인덱스)까지만, git 안 건드림  ← 게이트 검증용
  --no-verify 라이브 URL 확인 스킵(호출측 WebFetch로 검증)

주의: config.json 의 pageRepoPath 는 시그마(윈도) 경로일 수 있으니 맥에선 --page-repo 를 명시한다.
"""
from __future__ import annotations
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd, cwd=None, ctx=""):
    """subprocess 실행 — 실패 시 명확한 에러로 종료(트랩#6 외부실패 침묵 방지)."""
    r = subprocess.run(cmd, cwd=cwd)
    if r.returncode != 0:
        sys.exit(f"ERROR: {ctx or cmd[0]} 실패 (exit {r.returncode})")
    return r


def git_porcelain(cwd) -> str:
    return subprocess.run(["git", "status", "--porcelain"], cwd=cwd,
                          capture_output=True, text=True).stdout.strip()


def load_cfg(script_dir: Path) -> dict:
    for name in ("config.json", "config.example.json"):
        p = script_dir / name
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
    return {}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="MD 보고서를 GitHub Pages에 발행")
    ap.add_argument("--report", required=True, help="발행할 report.md 경로")
    ap.add_argument("--type", required=True, choices=["weekly", "interim"])
    ap.add_argument("--slug", required=True)
    ap.add_argument("--page-repo", default=None, help="page 레포 경로(맥은 명시 권장)")
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--no-verify", action="store_true")
    ap.add_argument("--no-push", action="store_true", help="commit 까지만, push 안 함")
    ap.add_argument("--no-git", action="store_true", help="파일 생성까지만(검증용)")
    a = ap.parse_args(argv)

    script_dir = Path(__file__).resolve().parent          # workflow/
    cfg = load_cfg(script_dir)

    page_repo = a.page_repo or cfg.get("pageRepoPath")
    if not page_repo:
        sys.exit("ERROR: --page-repo 미지정 (config.json pageRepoPath 도 없음)")
    page_repo = Path(page_repo).expanduser()
    base_url = (a.base_url or cfg.get("pageBaseUrl")
                or "https://charde023.github.io/page").rstrip("/")

    report = Path(a.report).expanduser().resolve()
    if not report.is_file():
        sys.exit(f"ERROR: report 없음: {report}")
    if not page_repo.is_dir():
        sys.exit(f"ERROR: page 레포 없음: {page_repo} (맥 경로를 --page-repo 로 지정했나?)")

    print(f"report   : {report}")
    print(f"type     : {a.type}")
    print(f"slug     : {a.slug}")
    print(f"page repo: {page_repo}")
    print(f"base url : {base_url}")

    # Step 1 — 목적지 폴더
    dest_dir = page_repo / "reports" / a.type / a.slug
    dest_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n==> dest: {dest_dir}")

    # Step 2 — report.md 복사
    dest_md = dest_dir / "report.md"
    shutil.copy2(report, dest_md)
    print(f"copied -> {dest_md}")

    # Step 3 — index.html 생성
    make_html = script_dir / "_template" / "make_report_html.py"
    if not make_html.is_file():
        sys.exit(f"ERROR: make_report_html.py 없음: {make_html}")
    run([sys.executable, str(make_html), "--input", str(dest_md), "--base-url", base_url],
        ctx="make_report_html.py")
    dest_html = dest_dir / "index.html"
    if not dest_html.is_file():
        sys.exit("ERROR: index.html 미생성")
    print(f"generated: {dest_html}")

    # Step 4 — 인덱스 재생성 (page_repo 전체 스캔)
    upd = script_dir / "update_reports_index.py"
    if not upd.is_file():
        sys.exit(f"ERROR: update_reports_index.py 없음: {upd}")
    run([sys.executable, str(upd), str(page_repo), base_url], ctx="update_reports_index.py")

    live = f"{base_url}/reports/{a.type}/{a.slug}/"

    if a.no_git:
        print(f"\n[--no-git] 파일 생성까지 완료(git 스킵). live(예정): {live}")
        return 0

    # Step 5 — git add / commit / pull --rebase / push
    run(["git", "add", "reports/"], cwd=str(page_repo), ctx="git add")
    if not git_porcelain(str(page_repo)):
        print("변경 없음 — 이미 최신.")
    else:
        run(["git", "commit", "-m", f"report: add {a.type}/{a.slug}"],
            cwd=str(page_repo), ctx="git commit")
        if a.no_push:
            print("[--no-push] 로컬 커밋까지 완료(push 스킵).")
        else:
            print("pull --rebase ...")
            run(["git", "pull", "--rebase", "origin", "main"],
                cwd=str(page_repo), ctx="git pull --rebase")
            print("push ...")
            r = subprocess.run(["git", "push", "origin", "main"], cwd=str(page_repo))
            if r.returncode != 0:
                print("push 실패 — pull 재시도 후 재푸시 ...")
                run(["git", "pull", "--rebase", "origin", "main"],
                    cwd=str(page_repo), ctx="git pull --rebase(재)")
                run(["git", "push", "origin", "main"], cwd=str(page_repo), ctx="git push(재)")
            print("pushed.")

    print("\n" + "=" * 60)
    print("PUBLISHED")
    print(f"  type : {a.type}")
    print(f"  slug : {a.slug}")
    print(f"  live : {live}")
    print(f"  index: {base_url}/reports/{a.type}/")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
