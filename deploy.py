import vertexai
from vertexai import agent_engines
from vertexai.preview import reasoning_engines
import os
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv(dotenv_path="bigquery_agent/.env")

# --- 設定 ---
# 環境変数から読み込み、ユーザーが入力するためのプレースホルダーを設定
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
STAGING_BUCKET = f"gs://{os.getenv('STAGING_BUCKET')}"
DEPLOY_DISPLAY_NAME = "BigQuery Agent"

# デプロイされたエージェントの環境変数
# 注意: GOOGLE_CLOUD_PROJECT と GOOGLE_CLOUD_LOCATION はデプロイ環境で自動的に設定されるため、
# 明示的に渡すべきではありません。
# 開発環境(adk web)ではADCによる認証を行いますが、デプロイ後はADC認証を禁止します
DEPLOY_ENVIRONMENT = {
    "GOOGLE_GENAI_USE_VERTEXAI": os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "True"),
    "ENV": "production",
}

# --- メインのデプロイロジック ---

# agent.pyで定義されたエージェントをインポート
try:
    from bigquery_agent.agent import root_agent
    print("agent.pyから'root_agent'を正常にインポートしました")
except ImportError as e:
    print(f"エラー: 'root_agent'をインポートできませんでした。エラー: {e}")
    exit()

# requirements.txtから要件を読み込む
try:
    with open("requirements.txt", "r") as f:
        requirements = [line.strip() for line in f if line.strip()]
    print(f"要件が見つかりました: {requirements}")
except FileNotFoundError:
    print("エラー: requirements.txtが見つかりません。")
    exit()

# Vertex AI SDKを初期化
print(f"プロジェクト'{PROJECT_ID}'、ロケーション'{LOCATION}'、ステージングバケット'{STAGING_BUCKET}'でVertex AIを初期化しています...")
vertexai.init(project=PROJECT_ID, location=LOCATION, staging_bucket=STAGING_BUCKET)

# エージェントをAdkAppでラップ
print("AdkAppを作成しています...")
app = reasoning_engines.AdkApp(
    agent=root_agent,
    enable_tracing=True,
)

# デプロイ用にパッケージ化するファイルのリスト
extra_packages = ["bigquery_agent/agent.py"]
print(f"追加ファイルをパッケージ化しています: {extra_packages}")

# エージェントをデプロイ
print(f"表示名'{DEPLOY_DISPLAY_NAME}'でAgent Engineをデプロイしています")
remote_app = agent_engines.create(
    display_name=DEPLOY_DISPLAY_NAME,
    agent_engine=app,
    requirements=requirements,
    extra_packages=extra_packages,
    description="BigQueryテーブルをクエリできるエージェントで、ユーザーの承認が必要です。",
    env_vars=DEPLOY_ENVIRONMENT
)

print("\n" + "="*60)
print("デプロイが正常に送信されました！")
print("デプロイが完了するまで数分お待ちください。")
print(f"Reasoning Engineのリソース名: {remote_app.resource_name}")
print("最終的な登録ステップでは、この名前のID部分が必要になります。")
print("="*60 + "\n")

try:
    deployment_id = remote_app.resource_name.split('/')[-1]
    print(f"ADK_DEPLOYMENT_ID: {deployment_id}")
except Exception as e:
    print(f"デプロイIDを自動的に抽出できませんでした。上記のリソース名からコピーしてください。エラー: {e}")
