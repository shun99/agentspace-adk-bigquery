import os 
import requests
import json
import google.auth
from google.adk.tools.bigquery import query_tool
from google.adk.tools.bigquery.config import BigQueryToolConfig
from google.adk.tools.bigquery.config import WriteMode
from google.adk.tools import ToolContext
from google.adk.agents import LlmAgent
from google.oauth2.credentials import Credentials as OAuth2Credentials
from dotenv import load_dotenv

load_dotenv()

# The AUTH_ID must match the one registered in Agentspace
AUTH_ID = "bigquery-auth"

# BigQuery のプロジェクト ID
PROJECT_ID = os.getenv("BIGQUERY_PROJECT_ID")


def bigquery_toolset(query: str, tool_context: ToolContext) -> str:

    print(f"DEBUG: Attempting to retrieve access token with AUTH_ID: {AUTH_ID}")
    access_token = tool_context.state.get(f"temp:{AUTH_ID}")

    # --- LOCAL TESTING WORKAROUND ---
    application_default_credentials = None
    if not access_token:
        # ローカル環境でのテスト用に、環境変数 'ENV' が 'production' でない場合に ADC を試す
        if os.environ.get("ENV") != "production":
            print("DEBUG: Token not in tool_context and ENV is 'local', trying Application Default Credentials...")
            try:
                application_default_credentials, _ = google.auth.default()
            except google.auth.exceptions.DefaultCredentialsError:
                print("DEBUG: Application Default Credentials not found.")
                pass  # ADCが見つからなくてもエラーにしない
    # --------------------------------

    try:
        # 書き込みオペレーションが実行されるのを防ぐ
        tool_config = BigQueryToolConfig(write_mode=WriteMode.BLOCKED)

        credentials_object = None
        if access_token:
            credentials_object = OAuth2Credentials(token=access_token)
        elif application_default_credentials:
            credentials_object = application_default_credentials
        
        if not credentials_object:
            return "認証情報が見つかりません。サーバー環境ではaccess_tokenが必要です。ローカル環境ではADCを設定してください。"

        result = query_tool.execute_sql(
            project_id=PROJECT_ID,
            query=query,
            credentials=credentials_object,
            settings=tool_config,
            tool_context=tool_context,
        )
        return json.dumps(result, ensure_ascii=False, indent=2)


    except requests.exceptions.RequestException as e:
        error_message_for_llm = f"APIリクエストエラー: {e}"
        if e.response is not None:
            try:
                error_json = e.response.json()
                print(f"DEBUG: Full JSON error from API: {json.dumps(error_json)}")
                error_message_for_llm = f"API Error: {error_json.get('error', {}).get('message', 'Unknown error')}"
            except json.JSONDecodeError:
                print(f"DEBUG: Non-JSON error response from API: {e.response.text}")
                error_message_for_llm = f"API Error: {e.response.status_code} {e.response.reason}"
        else:
            print(f"DEBUG: RequestException with no response: {e}")

        return error_message_for_llm
    except Exception as e:
        return f"予期せぬエラーが発生しました: {e}"


# BigQuery を使うエージェント
root_agent = LlmAgent(
    model="gemini-2.5-flash",
    name="bigquery_agent",
    instruction=f"""
    あなたは BigQuery のデータ分析をするエージェントです。
    tools である `bigquery_toolset` を使って SQL を実行し、データを取得・分析してユーザーからの質問に回答を生成します。
    BigQuery ジョブはプロジェクト ID `{PROJECT_ID}` で実行します。
    """,
    description="BigQuery のデータ分析をするエージェント",
    tools=[bigquery_toolset],
)
