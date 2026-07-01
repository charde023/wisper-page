"""코덱스 프록시(localhost:18080) OpenAI-호환 클라이언트.

ChatGPT 구독 경유 → 종량0. 인증은 프록시가 ~/.codex(ChatGPT 로그인)를 사용하므로
api_key는 더미면 된다. launchd(kr.apom.codex-proxy 류)로 상시 가동.

★ 방침: headless `claude -p`(유료 종량)는 쓰지 않는다. LLM은 이 프록시 또는 로컬 LLM.
"""
from __future__ import annotations

import os
import urllib.request

BASE = os.environ.get("CODEX_PROXY_BASE", "http://127.0.0.1:18080/v1")

# 교정=빠른 mini, 노트화=고품질. 필요시 환경변수로 오버라이드.
MODEL_CLEAN = os.environ.get("TB_MODEL_CLEAN", "gpt-5.4-mini")
MODEL_NOTE = os.environ.get("TB_MODEL_NOTE", "gpt-5.5")

_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI  # 지연 임포트

        _client = OpenAI(base_url=BASE, api_key="codex-proxy-dummy")
    return _client


def healthy() -> bool:
    """프록시가 살아있고 gpt-5 계열 모델을 노출하는지 확인."""
    try:
        with urllib.request.urlopen(BASE.rstrip("/") + "/models", timeout=5) as r:
            return b"gpt-5" in r.read()
    except Exception:
        return False


def chat(model: str, system: str, user: str, max_retries: int = 2) -> str:
    """단일 chat completion. 실패 시 재시도.

    코덱스 프록시(gpt-5 계열)는 temperature 등 샘플링 파라미터를 받지 않으므로
    보내지 않는다.
    """
    client = _get_client()
    last = None
    for _ in range(max_retries + 1):
        try:
            r = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            return r.choices[0].message.content or ""
        except Exception as exc:  # noqa: BLE001
            last = exc
    raise RuntimeError(f"codex-proxy chat 실패({model}): {last}")


if __name__ == "__main__":
    print("healthy:", healthy())
    if healthy():
        print(chat(MODEL_CLEAN, "You are terse.", "Reply with exactly: OK"))
