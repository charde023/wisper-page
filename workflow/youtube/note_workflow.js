export const meta = {
  name: 'techbridge-notes',
  description: 'Write Korean study notes to Obsidian from transcribed TechBridge-KR videos (one Sonnet executor per video)',
  phases: [{ title: 'Notes', detail: 'one agent per video: read transcript+youtube.json, write learning note to vault' }],
}

// args = { vaultDir, workspacesRoot, ids }  — with hardcoded fallbacks so the run is robust.
let A = args
if (typeof A === 'string') { try { A = JSON.parse(A) } catch (e) { A = {} } }
A = A || {}

const DEFAULT_IDS = [
  "mEmq6NFaFdQ", "cx6yo_z6GiI", "zIbSNV2htgw", "adIV8wlAFFE", "k9r2pIYYV9k", "HUqAH7FzY90",
  "nldkPgp3aIA", "H95cVsPJLcw", "_m18_bgqfIw", "HG7tSGouQOk", "0QsCi1vFcuM", "DHdgUBJ_v10",
  "vUL5DWs-hIQ", "hIlSFxVXUW0", "ghVrnyRPMcg", "TY96cXzS2cg", "YyZaX95erOs", "-mer0_qTj2A",
  "diF0Qbj56ys", "qPXd--Xqc4c", "xOSrKwPpH9Y", "9R1bX7L-YFo", "7t-DbGeek9U", "QY8zPglmLrI",
  "OmvU-bh1oMY", "SECE_Lqulu0", "_ZMAMPC4eLI", "7ydv-L3A0Xc", "rDLsTeuV0O8", "odHYuAWGZQA",
  "ufr6er69kLs", "QRtg2VrDO9g", "Q5_a3B49E8U", "CNcVW8qUZLQ", "woiuEUEAuE8", "OzCE6CWaSVY",
  "PZxzX9CbP3U", "DTjwCUs1qlw", "yGyZE0CQTM4", "G4JxyIDRd3M", "lrq6keaBIj0", "rxhqnqQh8MA",
  "-pqyzBxddyg", "AvmXPcU2jKA", "S25jE1HZnZQ", "E3CUMPzrsCM", "xv5nF747GEw", "GaVoI5ZxV10",
]
const vaultDir = A.vaultDir || "C:/workspace/obsidian/charde_n/학습노트/TechBridge-KR"
const wsRoot = A.workspacesRoot || "C:/workspace/wisper-page/workspaces"
const ids = (Array.isArray(A.ids) && A.ids.length) ? A.ids : DEFAULT_IDS
log(`args typeof=${typeof args} ids=${ids.length} vault=${vaultDir}`)
const videos = ids.map((id) => ({ id, ws: `${wsRoot}/yt-${id}` }))

const NOTE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['file', 'title', 'creator', 'summary', 'ok'],
  properties: {
    file: { type: 'string', description: 'Filename written (with .md)' },
    title: { type: 'string' },
    creator: { type: 'string', description: 'original_creator filled (or empty)' },
    summary: { type: 'string', description: 'one-line summary used in index' },
    ok: { type: 'boolean', description: 'true if the note was written successfully' },
  },
}

function promptFor(v) {
  return `You are writing ONE Korean study note for 차드's Obsidian vault from a transcribed YouTube talk.
This is from TechBridge-KR, a Korean curation channel re-posting AI/dev talks. The audio is USUALLY English
(sometimes Korean — channel narration/dubbing). The transcript reflects whatever was spoken. Your note must be in KOREAN.

READ THESE FILES (use the Read tool):
- Transcript (Whisper output): ${v.ws}/transcript.txt
- Metadata + provenance:        ${v.ws}/youtube.json
  (fields: title, raw_title, url, upload_date [YYYYMMDD], view_count, duration_min, channel, description,
   provenance{creator, affiliation, social_links, other_links})

WRITE the note (use the Write tool) to EXACTLY this folder (forward slashes are fine):
  ${vaultDir}/<FILENAME>.md
- <FILENAME> = a concise, descriptive Korean title from youtube.json.title with any "[한글자막]"/"[한국어더빙]" prefix stripped.
  Sanitize illegal filename chars ( \\ / : * ? " < > | ) by replacing with a space or hyphen. Keep it readable.
  If an external speaker is clearly named, you MAY append " (이름)". Keep under ~80 chars.

DETERMINE original_creator / affiliation / links YOURSELF from:
  (1) the title's "이름(소속)" or "— Name, Org" credit, (2) youtube.json.description social links,
  (3) the speaker's self-introduction in the transcript ("I'm X from Y").
  Do NOT trust youtube.json.provenance.creator blindly — it is a rough regex hint and is sometimes wrong
  (e.g. it may say "Claude Code"). If this is a generic channel tutorial with no external guest speaker,
  leave original_creator empty (the channel host is not the "original creator").

NOTE FORMAT — follow this skeleton EXACTLY (it is the vault standard):

---
title: <제목 — 접두 제거>
channel: TechBridge-KR
original_creator: <화자/원작자 또는 빈칸>
original_affiliation: <소속 또는 빈칸>
original_links: [<설명의 화자 SNS/제품 링크들>]
video_id: ${v.id}
url: <youtube.json.url>
upload_date: <YYYY-MM-DD  (youtube.json.upload_date 는 YYYYMMDD)>
duration_min: <youtube.json.duration_min>
status: 정리완료
created: 2026-06-06
summary: <한 줄 요약 — 목차 인덱스에 노출>
tags: [학습노트, techbridge-kr, 정리노트, <토픽 태그 2-4개>]
aliases: [<영문 원제 등>]
related: []
---

# <제목>

> [!summary] 한 줄 요약
> <영상 핵심 한 문장>

> [!info] 영상 정보
> 원작자 <이름> · <소속> · 추정 출처 <링크> · 업로드 <YYYY-MM-DD> · <길이>분 · 전사 Whisper large-v3 (auto)

---

## 핵심 학습 포인트 (내가 배워야 할 것)
| 개념 | 왜 중요한가 | 한 줄 |
표로 3-7개. 차드가 새로 알거나 익혀야 할 것.

## 내가 모를 만한 것 / 처음 보는 것
용어·도구·기법 불릿. 짧은 설명. (재사용 개념은 [[용어노트]]로 표시만)

## 화자의 디테일 (놓치기 쉬운 포인트)
> 화자가 흘리듯 말한 구체 수치·금액·명령어·설정값·도구명·의견. 번호목록. 원어 용어 괄호 병기, 맥락까지. 이 섹션이 가장 중요하다.

## 한눈에 보기
| # | 섹션 | 요지 |  (영상 흐름 순)

## 1. ~ ## N.
본문 요지 (영상 흐름대로, 상세). 화자 주장·예시·반론 포함.

## 종합 체크리스트
- [ ] 적용/실험해볼 것

> [!cite] 출처
> TechBridge-KR <raw_title> · <url> · 전사: Whisper large-v3 (auto)

---

## 교정 전사 (한국어)
> [!note]- 전체 전사 펼치기
> <영어 원문이면 한국어로 충실히 교정·번역(핵심 영어 용어 괄호 병기). 이미 한국어 전사면 오인식·말더듬만 교정. 중복 압축하되 모든 실질 내용 보존. 음성인식 의심 단어 [?원문]. 매우 긴 영상(40분+)은 더 압축해도 되나 distinct 포인트는 다 남길 것.>

POLICY (엄수):
- 한국어. Whisper 오인식을 문맥으로 교정 (예: Cloud→Claude, slot→slop, towery→Tauri, context seven→Context7, Gary→Garry Tan). 진짜 불확실하면 [?원문].
- 학습 헤더(핵심 학습 포인트 / 내가 모를 만한 것 / 화자의 디테일)가 노트의 핵심. 화자의 구체 디테일을 최대한 캐치.
- 이모지 절대 금지. 강조 스팬 2종만: 1차 <span style="color:#ef6c00; font-size:1.1em">**...**</span>, 2차 <span style="font-size:1.1em">**...**</span>. ==하이라이트== 금지. 코드/명령어는 백틱.
- 표·구조화 우선. 모바일 가독성: 위에서 아래로 상세해짐.

After writing the file, return the result object. Set ok=false only if you could not read the transcript.`
}

phase('Notes')

const results = await parallel(
  videos.map((v) => () =>
    agent(promptFor(v), {
      label: `note:${v.id}`,
      phase: 'Notes',
      model: 'sonnet',
      schema: NOTE_SCHEMA,
    }).then((r) => ({ ...r, id: v.id })).catch(() => ({ ok: false, id: v.id, file: '', title: '', creator: '', summary: '' }))
  )
)

const ok = results.filter((r) => r && r.ok)
log(`notes written: ${ok.length}/${videos.length}`)
return results
