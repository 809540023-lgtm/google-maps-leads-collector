# Google Maps Leads Collector

Google Maps Leads Collector is a FastAPI and Expo app for building a searchable phone lead database from Google Maps scraper output. It supports arbitrary global centers: address, place name, direct latitude/longitude, or Google Maps URL.

## Published Workflow

中文版：
若要進行全球數據收集，無論目標地點是否有明確地址，系統都能自動將其轉換為經緯度座標，再以該座標為中心進行精準搜尋。適合用於國際市場的商家、工廠或服務據點資料收集。

反向中文版：
就算沒有地址，也能以任意地點（如知名景點、商業區或特定座標）為中心，自動轉換為經緯度後進行全球範圍的資料收集。無需實際地址即可啟動搜尋流程。

日文版：
グローバルなデータ収集を行う際、対象地点に明確な住所がなくても、システムが自動で緯度経度に変換し、その座標を中心とした正確な検索が可能です。国際市場の店舗・工場・サービス拠点のデータ収集に最適です。

## What It Does

- Converts addresses, place names, coordinates, or Google Maps URLs into a collection center.
- Builds `gosom/google-maps-scraper` commands for radius, simple, and grid searches.
- Imports scraper JSON or CSV output.
- Normalizes Taiwan phone numbers, removes duplicates, and grades leads by distance.
- Stores leads and jobs in JSON locally, or PostgreSQL when `GOOGLE_MAPS_LEADS_STORAGE_BACKEND=postgres`.
- Exposes a browser dashboard, CSV/JSON exports, and JSON APIs for the Expo iOS/Android/Web client.

## Local API

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn api:app --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/google-maps-leads`.

## Mobile And Web Client

```bash
cd google-maps-leads-mobile
npm ci
npm run ios
npm run android
npm run web
```

The app defaults to `http://127.0.0.1:8000` for iOS and web, and `http://10.0.2.2:8000` for Android emulators. On Render, set `EXPO_PUBLIC_API_BASE_URL` to the deployed API URL.

## iOS And Android Downloads

The mobile app is ready for Expo EAS builds:

```bash
cd google-maps-leads-mobile
npm run build:android:apk
npm run build:ios:preview
```

Use `build:android:apk` for a directly downloadable Android APK. Use `build:ios:preview` for an internal iOS build through Apple/TestFlight or Ad Hoc provisioning. For iOS simulator testing, use:

```bash
npm run build:ios:simulator
```

After EAS returns build URLs, set these Render environment variables on the static site:

- `EXPO_PUBLIC_ANDROID_DOWNLOAD_URL`
- `EXPO_PUBLIC_IOS_DOWNLOAD_URL`
- `EXPO_PUBLIC_RELEASES_URL`

The app's Settings tab will show Android, iOS, and GitHub Releases download buttons automatically.

## Render

This repo includes `render.yaml` with two services:

- `emily77-google-maps-leads-api`: FastAPI backend.
- `emily77-google-maps-leads-mobile`: Expo web static export.

Render Blueprint setup:

1. Push this repository to GitHub.
2. In Render, choose **New > Blueprint**.
3. Connect this repository and select the `main` branch.
4. Deploy the Blueprint.

## Data Safety

The public repo intentionally starts with an empty `data/google_maps_leads_store.json`. Keep scraped phone lists and raw `gmaps-output` files private unless you have a lawful basis and permission to publish them.
