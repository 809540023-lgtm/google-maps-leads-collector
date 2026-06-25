from __future__ import annotations

from dataclasses import dataclass, field


PROHIBITED_AUTOMATION = [
    "不自動登入 Facebook",
    "不自動加入 Facebook 社團",
    "不自動大量發文",
    "不自動私訊社團成員",
    "不自動擷取個人資料",
    "不繞過 Facebook 社團規則或審核機制",
]


TOOL_SELECTION = {
    "primary_tool": "browser-use/browser-use",
    "primary_tool_url": "https://github.com/browser-use/browser-use",
    "primary_tool_reason": "GitHub stars 最高的 AI browser agent 類工具，適合協助理解公開頁面與整理候選資訊。",
    "assistant_tool": "Record & Replay",
    "assistant_tool_reason": "用於錄製真人示範的搜尋、判斷與整理流程，之後轉成可重複使用的 Codex skill。",
    "second_phase_tool": "microsoft/playwright-mcp",
    "second_phase_reason": "保留作為第二階段可控重播、驗證與測試工具。",
}


@dataclass(frozen=True)
class FacebookAgentInput:
    region: str
    industry: str
    store_type: str = ""
    target_audience: str = ""
    offer: str = ""
    line_official_account: str = ""
    business_name: str = ""


@dataclass(frozen=True)
class FacebookGroupCandidate:
    group_name: str
    region: str = ""
    group_type: str = ""
    member_count: int = 0
    post_activity: str = "unknown"
    latest_post_recency_days: int | None = None
    commercial_post_tolerance: str = "unknown"
    ads_allowed: str = "unknown"
    post_requires_review: str = "unknown"
    join_difficulty: str = "unknown"
    target_fit: str = "unknown"
    notes: str = ""


@dataclass(frozen=True)
class FacebookGroupRecommendation:
    group_name: str
    score: int
    priority: str
    suggested_operation: str
    reasons: list[str] = field(default_factory=list)
    safety_notes: list[str] = field(default_factory=list)


def _unique(items: list[str], limit: int = 50) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []
    for item in items:
        value = " ".join(item.split()).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        results.append(value)
        if len(results) >= limit:
            break
    return results


def generate_facebook_group_keywords(payload: FacebookAgentInput) -> list[str]:
    region = payload.region.strip()
    industry = payload.industry.strip()
    store_type = payload.store_type.strip() or industry
    target_audience = payload.target_audience.strip()

    base = [
        f"{region} 大小事",
        f"{region} 美食",
        f"{region} 店家",
        f"{region} 生活圈",
        f"{region} 在地人",
        f"{region} 好康",
        f"{region} 團購",
        f"{region} 媽媽",
        f"{region} 親子",
        f"{region} 上班族",
        f"{region} 公司午餐",
        f"{region} 團體便當",
        f"{region} 商家交流",
        f"{region} 店家互助",
        f"{region} 創業",
        f"{region} 老闆交流",
    ]

    industry_terms = {
        "餐飲": ["餐飲老闆", "餐飲老闆交流", "餐廳經營", "團體便當", "公司午餐", "外送美食", "午餐推薦", "晚餐推薦"],
        "飲料": ["飲料店經營", "手搖飲經營", "咖啡店經營", "下午茶", "辦公室團購", "公司下午茶"],
        "美容": ["美容美業創業", "美甲店經營", "美睫店經營", "美容行銷", "預約制店家"],
        "補習": ["補習班經營", "安親班招生", "才藝教室招生", "家長交流", "親子活動"],
        "診所": ["診所行銷", "牙醫行銷", "醫美行銷", "健康服務", "預約提醒"],
        "零售": ["零售店經營", "實體店面經營", "開店經營", "會員經營", "商家互助"],
    }
    selected_terms: list[str] = []
    for key, values in industry_terms.items():
        if key in industry or key in store_type:
            selected_terms.extend(values)
    if not selected_terms:
        selected_terms.extend(["開店經營", "老闆交流", "中小企業", "商家互助", "實體店面經營"])

    business_terms = [
        "餐飲老闆",
        "開店經營",
        "老闆交流",
        "中小企業",
        "商家互助",
        "創業交流",
        "實體店面經營",
    ]
    audience_terms = [f"{region} {target_audience}"] if target_audience else []
    local_industry_terms = [f"{region} {term}" for term in selected_terms[:12]]
    return _unique(base + local_industry_terms + selected_terms + business_terms + audience_terms, limit=50)


def recommend_group(candidate: FacebookGroupCandidate, target_region: str = "", target_audience: str = "") -> FacebookGroupRecommendation:
    reasons: list[str] = []
    score = 0
    group_name = candidate.group_name.strip()
    region_text = f"{candidate.region} {group_name}".lower()
    target_region = target_region.strip().lower()

    if target_region and target_region in region_text:
        score += 1
        reasons.append("地區高度符合")
    if candidate.member_count >= 1000:
        score += 1
        reasons.append("成員數充足")
    if candidate.post_activity == "high" or (
        candidate.latest_post_recency_days is not None and candidate.latest_post_recency_days <= 3
    ):
        score += 1
        reasons.append("近期發文活躍")
    if candidate.commercial_post_tolerance == "high" or candidate.ads_allowed == "yes":
        score += 1
        reasons.append("可接受商業或優惠內容")
    if candidate.target_fit == "high" or (
        target_audience and target_audience.lower() in f"{candidate.group_type} {candidate.notes}".lower()
    ):
        score += 1
        reasons.append("目標客群符合")

    score = min(max(score, 1), 5)
    if score >= 5:
        priority = "優先經營"
        suggested_operation = "先閱讀社團規則，再由人工安排互動文或優惠文曝光。"
    elif score == 4:
        priority = "可安排曝光"
        suggested_operation = "由人工確認是否允許商業內容，再安排低頻曝光。"
    elif score == 3:
        priority = "先觀察再操作"
        suggested_operation = "先觀察近期貼文與版規，必要時改用留言互動或洽詢版主。"
    else:
        priority = "低優先或不建議"
        suggested_operation = "暫不發文；只保留作為候選或排除名單。"

    safety_notes = [
        "人工確認社團規則後才可操作",
        "不得跨社團大量複製貼文",
        "不得自動加入、發文、留言或私訊",
    ]
    return FacebookGroupRecommendation(
        group_name=group_name,
        score=score,
        priority=priority,
        suggested_operation=suggested_operation,
        reasons=reasons or ["資料不足，需人工補充觀察"],
        safety_notes=safety_notes,
    )


def draft_facebook_posts(payload: FacebookAgentInput) -> dict[str, str]:
    business_name = payload.business_name.strip() or "我們店"
    region = payload.region.strip()
    industry = payload.industry.strip() or payload.store_type.strip() or "在地服務"
    offer = payload.offer.strip() or "在地朋友限定優惠"
    line = payload.line_official_account.strip() or "LINE 官方帳號"

    return {
        "地區生活社團": (
            f"大家好，我們是 {region} 附近的 {business_name}，主要提供 {industry} 服務。\n\n"
            f"最近想讓更多附近居民認識我們，所以準備了「{offer}」。如果你住在、上班在或常經過 {region}，"
            f"歡迎先透過 {line} 詢問。\n\n"
            "如果不符合社團規定，也請版主提醒，我們會配合調整，謝謝。"
        ),
        "美食社團": (
            f"{region} 附近的朋友，如果最近想找 {industry}，可以參考看看 {business_name}。\n\n"
            f"這次準備的活動是：{offer}。\n"
            f"想先了解菜單、預訂或詢問活動內容，可以透過 {line} 聯繫。\n\n"
            "我們會配合社團規範，不洗版、不重複張貼。"
        ),
        "上班族社團": (
            f"{region} 附近上班的朋友，如果公司午餐、下午茶或團體需求需要 {industry}，"
            f"{business_name} 可以協助安排。\n\n"
            f"目前活動：{offer}。\n"
            f"可先透過 {line} 詢問可服務範圍與預訂方式。\n\n"
            "若社團不開放商業合作文，也請版主提醒，我們會配合刪除或調整。"
        ),
    }


def build_record_and_replay_runbook() -> list[str]:
    return [
        "由使用者手動示範一次 Facebook 社團搜尋流程。",
        "錄製內容包含：搜尋關鍵字、閱讀社團名稱、查看社團規則、判斷是否適合、填入推薦表。",
        "錄製時不要輸入密碼、驗證碼、個資或任何敏感資訊。",
        "錄製完成後，Codex 讀取事件紀錄，整理成可重複使用的社團營運 skill。",
        "skill 只描述人工輔助流程，不包含自動登入、自動加入、自動發文或自動私訊。",
    ]


def build_facebook_agent_plan(
    payload: FacebookAgentInput,
    candidates: list[FacebookGroupCandidate] | None = None,
) -> dict[str, object]:
    candidates = candidates or []
    return {
        "tool_selection": TOOL_SELECTION,
        "safety_boundaries": PROHIBITED_AUTOMATION,
        "inputs": {
            "region": payload.region,
            "industry": payload.industry,
            "store_type": payload.store_type,
            "target_audience": payload.target_audience,
            "offer": payload.offer,
            "line_official_account": payload.line_official_account,
            "business_name": payload.business_name,
        },
        "keywords": generate_facebook_group_keywords(payload),
        "group_recommendations": [
            recommend_group(candidate, target_region=payload.region, target_audience=payload.target_audience).__dict__
            for candidate in candidates
        ],
        "post_drafts": draft_facebook_posts(payload),
        "daily_operation_checklist": [
            "確認店家資料、目標客群、優惠與 LINE 官方帳號。",
            "產生 20 至 50 組社團搜尋關鍵字。",
            "由真人搜尋 Facebook 社團並填寫候選名單。",
            "Agent 協助評分、分類與建議操作方式。",
            "真人確認社團規則與文案事實。",
            "真人決定是否發文、留言或洽詢版主。",
            "記錄曝光結果、LINE 加入數、詢問數、到店數與下一次建議。",
        ],
        "record_and_replay_runbook": build_record_and_replay_runbook(),
    }
