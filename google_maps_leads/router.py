from __future__ import annotations

import json
from html import escape
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse

from google_maps_leads.facebook_agent import FacebookAgentInput, FacebookGroupCandidate, build_facebook_agent_plan
from google_maps_leads.schemas import FacebookAgentPlanRequest, LeadCreate, LeadUpdate, ScrapeJobCreate
from google_maps_leads.store import DEFAULT_QUERY_TERMS, GoogleMapsLeadsStore, _split_tags, _split_terms

router = APIRouter(prefix="/google-maps-leads", tags=["google-maps-leads"])
store = GoogleMapsLeadsStore()


def _refresh_store() -> None:
    store._load()


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="zh-Hant">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escape(title)}</title>
    <style>
      :root {{
        --bg: #f7f8f5;
        --ink: #19201d;
        --muted: #68736e;
        --line: #d9dfda;
        --panel: #ffffff;
        --accent: #1b7f5f;
        --accent-2: #315c9f;
        --warn: #9b5b17;
        --danger: #a33b3b;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        background: var(--bg);
        color: var(--ink);
        font-family: "Avenir Next", "PingFang TC", "Noto Sans TC", Arial, sans-serif;
      }}
      a {{ color: inherit; }}
      .wrap {{ max-width: 1260px; margin: 0 auto; padding: 22px 18px 54px; }}
      .topbar {{ display: flex; justify-content: space-between; align-items: center; gap: 14px; margin-bottom: 18px; }}
      .brand {{ display: flex; align-items: center; gap: 11px; text-decoration: none; font-weight: 850; }}
      .mark {{ width: 38px; height: 38px; display: grid; place-items: center; background: var(--accent); color: #fff; border-radius: 8px; }}
      .nav {{ display: flex; flex-wrap: wrap; gap: 8px; }}
      .nav a, .button, button {{
        border: 1px solid var(--line);
        background: #fff;
        color: var(--ink);
        border-radius: 8px;
        padding: 9px 12px;
        text-decoration: none;
        font: inherit;
        font-weight: 750;
        cursor: pointer;
      }}
      .button.primary, button.primary {{ background: var(--accent); border-color: var(--accent); color: #fff; }}
      .button.secondary {{ background: var(--accent-2); border-color: var(--accent-2); color: #fff; }}
      .hero {{ display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(320px, .8fr); gap: 18px; align-items: stretch; margin-bottom: 18px; }}
      .panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 18px; }}
      h1 {{ margin: 0 0 10px; font-size: 34px; line-height: 1.12; letter-spacing: 0; }}
      h2 {{ margin: 0 0 14px; font-size: 22px; letter-spacing: 0; }}
      p {{ color: var(--muted); line-height: 1.62; margin: 8px 0; }}
      .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 10px; margin-top: 16px; }}
      .metric {{ border: 1px solid var(--line); border-radius: 8px; padding: 12px; background: #fbfcfa; }}
      .label {{ color: var(--muted); font-size: 12px; font-weight: 800; }}
      .value {{ margin-top: 6px; font-size: 28px; font-weight: 850; }}
      .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }}
      .form-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }}
      label {{ display: grid; gap: 6px; color: var(--muted); font-size: 13px; font-weight: 700; }}
      input, select, textarea {{
        width: 100%;
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 10px 11px;
        color: var(--ink);
        background: #fff;
        font: inherit;
      }}
      input[type="checkbox"], input[type="radio"] {{ width: auto; }}
      textarea {{ min-height: 92px; resize: vertical; }}
      .wide {{ grid-column: 1 / -1; }}
      .actions {{ display: flex; gap: 9px; flex-wrap: wrap; align-items: center; margin-top: 12px; }}
      .toolbar {{ display: flex; justify-content: space-between; gap: 12px; align-items: end; flex-wrap: wrap; margin-bottom: 12px; }}
      .filters {{ display: flex; gap: 8px; flex-wrap: wrap; align-items: end; }}
      table {{ width: 100%; border-collapse: collapse; background: #fff; }}
      th, td {{ padding: 11px 10px; border-bottom: 1px solid #edf0ed; text-align: left; vertical-align: top; font-size: 14px; }}
      th {{ color: var(--muted); background: #f3f6f3; font-size: 12px; text-transform: uppercase; }}
      .table-wrap {{ overflow: auto; border: 1px solid var(--line); border-radius: 8px; }}
      .muted {{ color: var(--muted); }}
      .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 12px; white-space: pre-wrap; overflow-wrap: anywhere; background: #f4f6f4; padding: 10px; border-radius: 8px; border: 1px solid var(--line); }}
      .chip {{ display: inline-flex; padding: 4px 7px; border-radius: 999px; background: #e7f3ee; color: var(--accent); font-size: 12px; font-weight: 800; margin: 2px; }}
      .status-new {{ color: var(--warn); font-weight: 850; }}
      .status-contacted {{ color: var(--accent-2); font-weight: 850; }}
      .status-qualified {{ color: var(--accent); font-weight: 850; }}
      .status-invalid {{ color: var(--danger); font-weight: 850; }}
      @media (max-width: 920px) {{
        .hero, .grid, .form-grid {{ grid-template-columns: 1fr; }}
        .metrics {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
        h1 {{ font-size: 28px; }}
      }}
    </style>
  </head>
  <body>
    <main class="wrap">
      <nav class="topbar">
        <a class="brand" href="/google-maps-leads"><span class="mark">☎</span><span>Google Maps 電話收集庫</span></a>
        <div class="nav">
          <a href="/google-maps-leads">資料庫</a>
          <a href="/google-maps-leads/jobs">收集任務</a>
          <a href="/google-maps-leads/export.csv">CSV</a>
          <a href="/google-maps-leads/export.json">JSON</a>
        </div>
      </nav>
      {body}
    </main>
  </body>
</html>"""


def _status_options(selected: str = "") -> str:
    options = ["", "new", "contacted", "qualified", "invalid"]
    labels = {"": "全部", "new": "新資料", "contacted": "已聯絡", "qualified": "可追蹤", "invalid": "無效"}
    return "".join(
        f'<option value="{escape(value)}" {"selected" if value == selected else ""}>{escape(labels[value])}</option>'
        for value in options
    )


def _search_mode_options(selected: str = "grid") -> str:
    labels = {
        "grid": "網格搜尋",
        "radius": "中心半徑",
        "simple": "文字搜尋",
    }
    return "".join(
        f'<option value="{escape(value)}" {"selected" if value == selected else ""}>{escape(label)}</option>'
        for value, label in labels.items()
    )


def _optional_float(value: str) -> float | None:
    try:
        return float(value) if value.strip() else None
    except ValueError:
        return None


@router.post("/api/facebook-agent/plan")
def facebook_agent_plan(payload: FacebookAgentPlanRequest) -> dict[str, object]:
    agent_input = FacebookAgentInput(
        region=payload.region,
        industry=payload.industry,
        store_type=payload.store_type,
        target_audience=payload.target_audience,
        offer=payload.offer,
        line_official_account=payload.line_official_account,
        business_name=payload.business_name,
    )
    candidates = [
        FacebookGroupCandidate(
            group_name=item.group_name,
            region=item.region,
            group_type=item.group_type,
            member_count=item.member_count,
            post_activity=item.post_activity,
            latest_post_recency_days=item.latest_post_recency_days,
            commercial_post_tolerance=item.commercial_post_tolerance,
            ads_allowed=item.ads_allowed,
            post_requires_review=item.post_requires_review,
            join_difficulty=item.join_difficulty,
            target_fit=item.target_fit,
            notes=item.notes,
        )
        for item in payload.candidate_groups
    ]
    return {"data": build_facebook_agent_plan(agent_input, candidates)}


@router.get("", response_class=HTMLResponse)
def index(q: str = "", status: str = "", phone_only: bool = False) -> str:
    _refresh_store()
    rows = store.list_leads(q=q, status=status, phone_only=phone_only)
    metrics = store.metrics()
    table_rows = "".join(
        f"""
        <tr>
          <td><strong>{escape(lead.name)}</strong><br><span class="muted">{escape(lead.category or "-")}</span></td>
          <td>{escape(lead.phone or "-")}<br><span class="muted">{escape(lead.email or "")}</span></td>
          <td>{escape(lead.address or "-")}<br>{f'<a href="{escape(lead.website)}" target="_blank">網站</a>' if lead.website else ''}</td>
          <td>{escape(str(lead.rating or "-"))}<br><span class="muted">{escape(str(lead.reviews or ""))} reviews</span></td>
          <td><strong>{escape(lead.lead_grade or "-")}</strong><br><span class="muted">{escape(lead.distance_band or "-")} {escape(str(round(lead.distance_m)) + "m" if lead.distance_m is not None else "")}</span></td>
          <td><span class="status-{escape(lead.status)}">{escape(lead.status)}</span><br>{''.join(f'<span class="chip">{escape(tag)}</span>' for tag in lead.tags)}</td>
          <td>
            <form method="post" action="/google-maps-leads/leads/{lead.id}/status" class="actions">
              <select name="status">{_status_options(lead.status)}</select>
              <button>更新</button>
            </form>
          </td>
        </tr>
        """
        for lead in rows
    ) or '<tr><td colspan="7" class="muted">還沒有資料。可以先建立收集任務，跑完 gosom scraper 後匯入 JSON/CSV。</td></tr>'
    body = f"""
      <section class="hero">
        <div class="panel">
          <h1>把 Google Maps 商家結果變成可追蹤的電話資料庫</h1>
          <p>先用地址轉中心點，再用半徑或網格搜尋建立名單。匯入後系統會用經緯度計算距離、統一電話格式、去重，並依 0-1km、1-3km、3-5km 自動分級。</p>
          <div class="metrics">
            <div class="metric"><div class="label">總資料</div><div class="value">{metrics["total"]}</div></div>
            <div class="metric"><div class="label">有電話</div><div class="value">{metrics["with_phone"]}</div></div>
            <div class="metric"><div class="label">有 Email</div><div class="value">{metrics["with_email"]}</div></div>
            <div class="metric"><div class="label">A 級</div><div class="value">{metrics["grade_a"]}</div></div>
            <div class="metric"><div class="label">B 級</div><div class="value">{metrics["grade_b"]}</div></div>
            <div class="metric"><div class="label">已聯絡</div><div class="value">{metrics["contacted"]}</div></div>
            <div class="metric"><div class="label">任務</div><div class="value">{metrics["jobs"]}</div></div>
          </div>
          <div class="actions">
            <a class="button primary" href="/google-maps-leads/jobs">建立收集任務</a>
            <a class="button secondary" href="/google-maps-leads/export.csv">匯出 CSV</a>
          </div>
        </div>
        <form class="panel" method="post" action="/google-maps-leads/import" enctype="multipart/form-data">
          <h2>匯入 scraper 結果</h2>
          <label>來源搜尋詞 <input name="source_query" placeholder="例如：台北 牙醫" /></label>
          <label>對應任務
            <select name="job_id">
              <option value="">不指定</option>
              {''.join(f'<option value="{job.id}">{escape(job.query)} {escape(job.location)}</option>' for job in store.list_jobs())}
            </select>
          </label>
          <label>CSV 或 JSON 檔 <input type="file" name="file" accept=".csv,.json,application/json,text/csv" required /></label>
          <div class="actions"><button class="primary" type="submit">匯入資料</button></div>
        </form>
      </section>
      <section class="grid">
        <form class="panel" method="post" action="/google-maps-leads/leads">
          <h2>手動新增</h2>
          <div class="form-grid">
            <label>商家名稱 <input name="name" required /></label>
            <label>電話 <input name="phone" /></label>
            <label>Email <input name="email" /></label>
            <label>網站 <input name="website" /></label>
            <label class="wide">地址 <input name="address" /></label>
            <label>分類 <input name="category" /></label>
            <label>標籤 <input name="tags" placeholder="高意願, 台北" /></label>
            <label class="wide">備註 <textarea name="notes"></textarea></label>
          </div>
          <div class="actions"><button class="primary" type="submit">新增</button></div>
        </form>
        <div class="panel">
          <h2>下一步接 scraper</h2>
          <p>Render 的 Python runtime 通常不能直接啟動 Docker 容器，所以這版先把 gosom 的輸出匯入做好。若要在雲端自動跑 scraper，建議改成背景 worker、外部 VPS，或改用 gosom REST API/獨立 Docker 服務後回寫這個資料庫。</p>
          <p>資料目前存放在 <span class="mono">data/google_maps_leads_store.json</span>，之後要切 PostgreSQL/Supabase 也很直覺。</p>
        </div>
      </section>
      <section class="panel" style="margin-top:18px;">
        <div class="toolbar">
          <h2>商家資料</h2>
          <form class="filters" method="get" action="/google-maps-leads">
            <label>搜尋 <input name="q" value="{escape(q)}" placeholder="名稱、電話、地址、標籤" /></label>
            <label>狀態 <select name="status">{_status_options(status)}</select></label>
            <label><span>只看有電話</span><input type="checkbox" name="phone_only" value="true" {"checked" if phone_only else ""} /></label>
            <button>篩選</button>
          </form>
        </div>
        <div class="table-wrap">
          <table>
            <thead><tr><th>商家</th><th>聯絡</th><th>位置/網站</th><th>評分</th><th>距離</th><th>狀態</th><th>操作</th></tr></thead>
            <tbody>{table_rows}</tbody>
          </table>
        </div>
      </section>
    """
    return _page("Google Maps 電話收集庫", body)


@router.get("/jobs", response_class=HTMLResponse)
def jobs() -> str:
    _refresh_store()
    default_terms = "\n".join(DEFAULT_QUERY_TERMS)
    job_rows = "".join(
        f"""
        <tr>
          <td><strong>{escape(job.query)}</strong><br><span class="muted">{escape(job.location or job.address or "-")}</span></td>
          <td>{escape(job.search_mode)}<br><span class="muted">{escape(job.geocode_status or "-")} {escape(job.geocode_source or "")}</span><br><span class="muted">imported: {job.imported_count}</span></td>
          <td>{escape(str(job.center_latitude or "-"))}, {escape(str(job.center_longitude or "-"))}<br><span class="muted">{escape(job.geocoded_address or "")}</span><br><span class="muted">bbox: {escape(job.grid_bbox or "-")}</span></td>
          <td><div class="mono">{escape(job.queries_text or "")}</div></td>
          <td><div class="mono">{escape(job.command)}</div><div class="mono">{escape(store.build_local_binary_command(job))}</div></td>
        </tr>
        """
        for job in store.list_jobs()
    ) or '<tr><td colspan="5" class="muted">尚未建立任務。</td></tr>'
    body = f"""
      <section class="grid">
        <form class="panel" method="post" action="/google-maps-leads/jobs">
          <h1>建立收集任務</h1>
          <div class="form-grid">
            <label>任務名稱 <input name="query" value="泰山楓江路周邊電話名單" required /></label>
            <label>搜尋模式 <select name="search_mode">{_search_mode_options("grid")}</select></label>
            <label class="wide">中心地點 / 地址 / 座標 / Maps URL <input name="address" value="新北市泰山區楓江路40-2號" placeholder="東京鐵塔、Shibuya Crossing、25.062426,121.434740、Google Maps URL" /></label>
            <label>搜尋地區文字 <input name="location" value="新北市泰山區楓江路" placeholder="可留空；例如 Tokyo, Shibuya, Taipei" /></label>
            <label>搜尋半徑 <input name="radius_m" type="number" value="3000" min="100" /></label>
            <label>最大保留距離 <input name="max_distance_m" type="number" value="5000" min="100" /></label>
            <label>Grid cell km <input name="grid_cell_km" type="number" value="0.4" min="0.1" step="0.1" /></label>
            <label>Zoom <input name="zoom" type="number" value="16" min="1" max="21" /></label>
            <label>深度 <input name="depth" type="number" value="10" min="1" max="30" /></label>
            <label>併發數 <input name="concurrency" type="number" value="4" min="1" max="12" /></label>
            <label>手動緯度 <input name="center_latitude" type="number" step="0.000001" placeholder="可留空自動 geocode" /></label>
            <label>手動經度 <input name="center_longitude" type="number" step="0.000001" placeholder="可留空自動 geocode" /></label>
            <label><span>抓 Email</span><input name="extract_email" type="checkbox" value="true" checked /></label>
            <label><span>匯入時距離過濾</span><input name="strict_distance_filter" type="checkbox" value="true" checked /></label>
            <label class="wide">queries.txt <textarea name="query_terms">{escape(default_terms)}</textarea></label>
            <label class="wide">備註 <textarea name="notes"></textarea></label>
          </div>
          <div class="actions"><button class="primary" type="submit">產生命令</button><a class="button" href="/google-maps-leads">回資料庫</a></div>
        </form>
        <div class="panel">
          <h2>全球中心點</h2>
          <p>無論是地址、景點、商業區、座標或 Google Maps 連結，系統都會先轉成經緯度，再以該座標為中心產生 radius 或 grid 搜尋命令。</p>
          <p>沒有明確地址也可以啟動，適合國際市場的商家、工廠、倉儲或服務據點資料收集。</p>
          <p>グローバルなデータ収集でも、住所がない地点を緯度経度に変換し、その座標を中心に検索できます。</p>
          <p>Render Web service 不適合直接啟動 Docker；正式自動化可把 gosom 放在 worker/VPS，或獨立部署它的 API，再把 JSON/CSV 回寫到這裡。</p>
        </div>
      </section>
      <section class="panel" style="margin-top:18px;">
        <h2>任務列表</h2>
        <div class="table-wrap"><table><thead><tr><th>搜尋</th><th>模式</th><th>中心/bbox</th><th>queries.txt</th><th>命令</th></tr></thead><tbody>{job_rows}</tbody></table></div>
      </section>
    """
    return _page("收集任務", body)


@router.post("/jobs")
def create_job(
    query: str = Form(...),
    location: str = Form(""),
    address: str = Form(""),
    search_mode: str = Form("grid"),
    query_terms: str = Form(""),
    center_latitude: str = Form(""),
    center_longitude: str = Form(""),
    radius_m: int = Form(3000),
    max_distance_m: int = Form(5000),
    grid_cell_km: float = Form(0.4),
    zoom: int = Form(16),
    concurrency: int = Form(4),
    max_results: int = Form(50),
    depth: int = Form(10),
    extract_email: bool = Form(False),
    strict_distance_filter: bool = Form(False),
    notes: str = Form(""),
) -> RedirectResponse:
    store.create_job(
        ScrapeJobCreate(
            query=query,
            location=location,
            address=address,
            search_mode=search_mode,
            query_terms=_split_terms(query_terms),
            center_latitude=_optional_float(center_latitude),
            center_longitude=_optional_float(center_longitude),
            radius_m=radius_m,
            max_distance_m=max_distance_m,
            grid_cell_km=grid_cell_km,
            zoom=zoom,
            concurrency=concurrency,
            max_results=max_results,
            depth=depth,
            extract_email=extract_email,
            strict_distance_filter=strict_distance_filter,
            notes=notes,
        )
    )
    return RedirectResponse("/google-maps-leads/jobs", status_code=303)


@router.post("/leads")
def create_lead(
    name: str = Form(...),
    phone: str = Form(""),
    email: str = Form(""),
    website: str = Form(""),
    address: str = Form(""),
    category: str = Form(""),
    tags: str = Form(""),
    notes: str = Form(""),
) -> RedirectResponse:
    store.create_lead(
        LeadCreate(
            name=name,
            phone=phone,
            email=email,
            website=website,
            address=address,
            category=category,
            tags=_split_tags(tags),
            notes=notes,
        )
    )
    return RedirectResponse("/google-maps-leads", status_code=303)


@router.post("/leads/{lead_id}/status")
def update_status(lead_id: UUID, status: str = Form(...)) -> RedirectResponse:
    if not store.update_lead(lead_id, LeadUpdate(status=status)):
        raise HTTPException(status_code=404, detail="Lead not found")
    return RedirectResponse("/google-maps-leads", status_code=303)


@router.post("/import")
async def import_file(
    file: UploadFile = File(...),
    source_query: str = Form(""),
    job_id: str = Form(""),
) -> RedirectResponse:
    raw = await file.read()
    parsed_job_id = UUID(job_id) if job_id else None
    filename = (file.filename or "").lower()
    if filename.endswith(".json"):
        store.import_json(raw, source_query=source_query, job_id=parsed_job_id)
    else:
        store.import_csv(raw, source_query=source_query, job_id=parsed_job_id)
    return RedirectResponse("/google-maps-leads", status_code=303)


@router.get("/api/leads")
def api_leads(q: str = "", status: str = "", phone_only: bool = False) -> list[dict[str, object]]:
    _refresh_store()
    return [lead.model_dump(mode="json") for lead in store.list_leads(q=q, status=status, phone_only=phone_only)]


@router.get("/api/metrics")
def api_metrics() -> dict[str, int]:
    _refresh_store()
    return store.metrics()


@router.post("/api/leads", status_code=201)
def api_create_lead(payload: LeadCreate) -> dict[str, object]:
    _refresh_store()
    lead = store.create_lead(payload)
    return lead.model_dump(mode="json")


@router.patch("/api/leads/{lead_id}")
def api_update_lead(lead_id: UUID, payload: LeadUpdate) -> dict[str, object]:
    _refresh_store()
    lead = store.update_lead(lead_id, payload)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead.model_dump(mode="json")


@router.get("/api/jobs")
def api_jobs() -> list[dict[str, object]]:
    _refresh_store()
    return [job.model_dump(mode="json") for job in store.list_jobs()]


@router.post("/api/jobs", status_code=201)
def api_create_job(payload: ScrapeJobCreate) -> dict[str, object]:
    _refresh_store()
    job = store.create_job(payload)
    return job.model_dump(mode="json")


@router.get("/export.csv")
def export_csv(q: str = "", status: str = "", phone_only: bool = False) -> PlainTextResponse:
    _refresh_store()
    csv_text = store.export_csv(store.list_leads(q=q, status=status, phone_only=phone_only))
    return PlainTextResponse(
        csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="google-maps-leads.csv"'},
    )


@router.get("/export.json")
def export_json(q: str = "", status: str = "", phone_only: bool = False) -> PlainTextResponse:
    _refresh_store()
    data = [lead.model_dump(mode="json") for lead in store.list_leads(q=q, status=status, phone_only=phone_only)]
    return PlainTextResponse(
        json.dumps(data, ensure_ascii=False, indent=2),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="google-maps-leads.json"'},
    )
