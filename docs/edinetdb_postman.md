# EDINET DB API を Postman で叩く

決算予定/決算内容などの EDINET DB (https://edinetdb.jp/v1) を Postman から検証するための
コレクションと環境ファイル。

## ファイル
- `docs/edinetdb.postman_collection.json` — リクエスト集（コレクション）
- `docs/edinetdb.postman_environment.json` — 変数（環境）

## セットアップ
1. Postman の **Import** で上記2ファイルを取り込む。
2. 右上の Environment セレクタで **「EDINET DB」** を選択。
3. 環境変数 **`api_key`** に発行済みのAPIキーを設定（`edb_...`）。
   ※キーはファイルに埋め込んでいない。リポジトリにコミットしないこと。
4. 任意で `edinet_code`（企業系のパス。EDINETコード。既定 E02144=トヨタ）や
   `sec_code`（calendar/events のフィルタ。既定 7203）、`from`/`to` を調整。

## 認証
- コレクション全体に `X-API-Key: {{api_key}}` を自動付与（`/status`・`/search` は認証不要）。
- `Authorization: Bearer <key>` でも可（EDINET DB 側の仕様）。

## 無料枠(100/日)の確認
- 各レスポンスのヘッダー `X-RateLimit-Remaining` / `X-Unit-Cost` を、コレクションの
  テストスクリプトが **Postman Console** に出力する（View → Show Postman Console）。
- 累計は **`01 利用状況 /usage`** で確認（daily_remaining / monthly_remaining）。

## まず見たいリクエスト
- **02 決算カレンダー /calendar** — カブログの日次同期が使う本体。`data.calendar[]` にネスト。
- **03 イベントフィード /events (earnings_summary)** — 全銘柄横断で「決算が出た」を安く取得。
  ここに売上/営業利益などヘッドライン数値が載っているかを確認したい（載っていれば個社取得が不要）。
- **06 決算短信 /companies/{edinet_code}/earnings** — 個社の決算詳細（1銘柄=1リクエスト）。

## コスト設計メモ
- 横断フィード（calendar / events）は**ピーク日でもリクエストほぼ一定**。
- 個社エンドポイント（earnings / financials / ratios / analysis）は**1銘柄=1リクエスト**。
  同日決算が100社を超える日でも無料枠に収めるため、対象を記録銘柄に限定し、
  遅延取得＋銘柄コード単位のキャッシュ＋日次上限で運用する（詳細は本セッションの検討メモ参照）。
