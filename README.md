# PostgreSQL Buffer Trace Visualizer

このプロジェクトは、PostgreSQLの共有バッファへのI/Oアクティビティをリアルタイムで可視化するツールです。`bpftrace`を使用してPostgreSQLのUSDTプローブをフックし、そのデータを`FastAPI`を介してブラウザにWebSocketでストリーミング配信します。クライアント側のJavaScriptは、各テーブルのバッファブロックをグリッド形式で表示し、アクセスがあったブロックをハイライトします。

PostgreSQLの内部動作を学習する教材として利用することを想定しています。

## ✨ 特徴

-   **リアルタイム可視化**: PostgreSQLのバッファI/Oを即座にCanvasに反映。
-   **テーブルごとのグリッド表示**: 各テーブルやインデックスごとに独立したCanvasにブロックグリッドを表示。
-   **テーブル/インデックス分離表示**: サイドバーでテーブルとインデックスを分けて表示し、選択可能。
-   **デフラグ風ハイライト**: アクセスがあったブロックを一時的にハイライト表示。requestAnimationFrameによる効率的な描画。
-   **データ永続化**: Docker名前付きボリュームによるPostgreSQLデータの永続化。
-   **Dockerで完結**: 簡単に環境構築・再現が可能。

## 🚀 動作要件

-   **Docker**: Docker Desktop (WSL2環境を推奨)
-   **Linux カーネル**: `bpftrace`およびBPFをサポートするカーネル (v4.9+、推奨 v5.x+) を搭載したLinux環境 (WSL2上のLinuxディストリビューションで動作します)。

## 📦 セットアップ

### Option A: Docker (Linux/WSL2)

### 1. リポジトリのクローン

```bash
git clone https://github.com/iakio/pgbftrace.git
cd pgbftrace
```

### 2. Dockerイメージのビルド

プロジェクトルートディレクトリで以下のコマンドを実行し、必要なツールと依存関係を含むDockerイメージをビルドします。

```bash
docker build -t bpftrace-dev .
```

### 3. コンテナの起動

`./bin/up.sh`スクリプトを実行して、FastAPIサーバーとPostgreSQLサービスを起動します。このスクリプトはコンテナに `pgbftrace_app` という名前を付け、PostgreSQLデータを永続化するための名前付きボリューム `pgbftrace_pgdata` を作成します。

```bash
./bin/up.sh
```

**注**: PostgreSQLのデータはDocker名前付きボリュームに保存されるため、コンテナを再起動してもデータは保持されます。データをクリアしたい場合は、以下のコマンドでボリュームを削除してください：

```bash
docker volume rm pgbftrace_pgdata
```

### Option B: Multipass (macOS)

macOSではeBPFが直接動作しないため、Multipassを使用してUbuntu VMを作成し、その中で実行します。

#### 1. Multipassのインストール

```bash
brew install multipass
```

#### 2. VMのセットアップ

```bash
./bin/multipass-setup.sh
```

このスクリプトは以下を行います：
- Ubuntu 22.04 VM (`pgbftrace`) を作成
- 必要なパッケージ (bpftrace, PostgreSQL, Node.js, Python) をインストール
- プロジェクトディレクトリをVMにマウント

#### 3. VMに接続してアプリを起動

```bash
# VMに接続
multipass shell pgbftrace

# アプリを起動
cd ~/pgbftrace
./bin/multipass-run.sh
```

#### 4. ブラウザでアクセス

VM の IP アドレスを確認して、ブラウザでアクセスします。

```bash
# Mac側で実行
multipass info pgbftrace | grep IPv4
```

`http://<VM_IP>:8000/` でアクセスできます。

#### VMの管理

```bash
# VM を停止
multipass stop pgbftrace

# VM を再起動
multipass start pgbftrace

# VM を削除
multipass delete pgbftrace && multipass purge
```

## 💡 使い方

### 1. ブラウザでアクセス

Webブラウザで以下のURLにアクセスします。

```
http://localhost:8000/
```

サイドバーにテーブルとインデックスが分けて一覧表示され、選択したリレーションのブロックがCanvas上にグリッド形式で表示されます。WebSocketへの接続も自動的に確立されます。

-   **🔄 Reloadボタン**: テーブル一覧の右上にあるReloadボタンをクリックすると、PostgreSQLから最新のテーブル情報を再取得できます。
-   **チェックボックス**: 各テーブル/インデックスの左にあるチェックボックスで、表示するリレーションを選択できます。

### 2. PostgreSQLを操作

別のターミナルを開き、以下のコマンドで実行中のコンテナに接続します。

```bash
docker exec -it pgbftrace_app /bin/bash
```

コンテナ内で`psql`クライアントを起動し、PostgreSQLデータベースに接続します。

```bash
psql -U postgres -d postgres
```

`psql`で様々な操作を行い、PostgreSQLのバッファI/Oを発生させます。

例:
-   **データ挿入**: `CREATE TABLE my_data (id SERIAL PRIMARY KEY, value TEXT);`
-   **大量データ挿入**: `INSERT INTO my_data (value) SELECT 'some data ' || generate_series(1, 100000);`
-   **データ読み込み**: `SELECT count(*) FROM my_data;`
-   **ページキャッシュのクリア (強制I/O)**: `psql`を終了 (`\q`または`Ctrl+D`) した後、コンテナのシェルで以下を実行し、再度`psql`に入って`SELECT`を実行。
    ```bash
    sudo sh -c "echo 3 > /proc/sys/vm/drop_caches"
    ```
    (注意: これは本番環境では絶対に実行しないでください)

### 3. 可視化の確認

`psql`で操作を行うと、ブラウザのCanvas上で対応するテーブルのブロックがリアルタイムでハイライト表示されます。

## 🛠️ 内部アーキテクチャ

このツールはモジュラーアーキテクチャで構成されており、以下のコンポーネントで動作します。

### **BPFトレーシング層**
-   **`bpftrace`**: PostgreSQLの`buffer__read__done` USDTプローブをフックし、`relfilenode` (arg4) と `block` (arg1) を取得。16進数固定長形式 (`%08x%08x`) で出力します。

### **Python バックエンド層**
-   **`main.py`**: FastAPIのルーティングとアプリケーション初期化を管理
-   **`config.py`**: 環境変数による設定管理（PostgreSQL接続、bpftraceパス等）
-   **`database.py`**: PostgreSQL操作とリレーション情報のキャッシュ管理
-   **`bpftrace_manager.py`**: bpftraceプロセスのライフサイクル管理と出力パース
-   **`websocket_manager.py`**: WebSocket接続の管理とブロードキャスト処理
-   **`models.py`**: データモデル定義（`TraceEvent`, `RelationInfo`）

### **API エンドポイント**
-   **HTTP `GET /api/relations`**: PostgreSQLからテーブル情報（`relkind`含む）を取得してJSON形式で提供。`relfilenode`キャッシュも更新。
-   **WebSocket `/ws`**: `bpftrace`からの16進数固定長出力（16文字）をパースし、キャッシュされた`relfilenode`のI/Oイベントのみをバイナリ形式でブロードキャスト。

### **フロントエンド層**
-   **React + TypeScript + Vite (プロダクションビルド)**:
    -   `GET /api/relations`で初期テーブル情報を取得し、`relkind`に基づいてテーブルとインデックスを分離表示
    -   各リレーションに対応するCanvasコンポーネントを動的に生成
    -   WebSocketで受信したバイナリデータをコールバック経由で処理し、対応するCanvasのブロックをハイライト表示
    -   requestAnimationFrameを使用した効率的なブロッククリア処理（再レンダリングゼロ）

## 📄 ライセンス

(もしあればここにライセンス情報を記述)
