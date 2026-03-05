import os
import yaml
import json
from google import genai
from google.genai import types


"""
Pass latest video url and ask Gemini to fetch content and summarize.
Result is not stable, because it always fetch wrong content.
"""


def load_api_key():
    secret_path = os.path.join('.', 'resources', 'secret.yml')
    with open(secret_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
        return config.get('GEMINI_API_KEY')

def summarize_youtube_video(video_url):
    client = genai.Client(api_key=load_api_key())

    # 強大的系統指令，確保輸出品質與您要求的範例一致
    system_instr = """
    你是一位頂尖的政經分析官。你的任務是分析使用者提供的 YouTube 影片。
    請嚴格遵守以下準則：
    1. 深度提取：挖掘影片中的具體數據、官員名稱、歷史典故與數據。
    2. 結構化輸出：必須分為「財經新聞」、「國際新聞」、「中國政治」等分類。
    3. IoT 觀點：總結影片中作者的獨特觀察與評論。
    4. 排除雜訊：不要寫任何開場白（例如：這是一份報告...），直接進入主題。
    """

    prompt = f"""
    請針對這支影片進行深度摘要與觀點提取：{video_url}
    
    摘要要求包含：
    - 影片完整標題。
    - 財經新聞（例如：關稅、石油、美聯儲政策）。
    - 國際新聞（例如：伊朗戰爭細節、美軍武器運用、地緣政治分析）。
    - 中國政治（例如：官員失聯原因分析、兩會觀察）。
    - 每個項目請詳細描述「事實內容」與「作者觀點」。
    """

    print(f"正在深度解析影片內容，請稍候...")

    try:
        # 直接傳送網址，不開啟 google_search 
        # Gemini 1.5 Pro 與 2.0/2.5 Flash 均支援直接處理 YouTube 網址
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite", # 或 gemini-2.5-flash-lite
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instr,
                temperature=0.2
            )
        )

        print("\n--- 深度總結結果 ---")
        if response.text:
            print(response.text)
        else:
            print("模型未回傳結果，可能是影片受限或無法存取。")

    except Exception as e:
        print(f"執行時發生錯誤: {e}")

if __name__ == "__main__":
    # 使用者手動輸入網址，確保抓到的是最新的一支
    url = input("請輸入 YouTube 影片網址: ")
    if url.strip():
        summarize_youtube_video(url)
    else:
        print("網址不能為空。")
        
        
"""
Passing Channel ID and ask Gemini to search latest video and summarize content.
The result is unstable because it always search wrong content.
"""


def load_api_key():
    secret_path = os.path.join('.', 'resources', 'secret.yml')
    with open(secret_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
        return config.get('GEMINI_API_KEY')

def get_high_quality_summary(channel_handle):
    client = genai.Client(api_key=load_api_key())
    
    # 步驟 1：精準定位最新影片 URL
    search_prompt = f"找出 YouTube 頻道 {channel_handle} 在 2026 年 3 月最新發布的一支影片網址與標題。"
    
    search_response = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=search_prompt,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())]
        )
    )
    
    # 步驟 2：針對該影片進行深度摘要
    # 我們將搜尋到的結果作為背景，下達極其嚴格的格式指令
    deep_prompt = f"""
    參考以下搜尋到的影片資訊：
    {search_response.text}
    
    任務：
    請針對這支「最新影片」的完整內容（包含逐字稿細節），進行深度專業的總結。
    
    要求格式：
    1. 使用 Markdown 格式。
    2. 分為「財經新聞」、「國際新聞」、「中國政治/社會新聞」等分類。
    3. 每個項目必須包含：
       - 具體事實陳述（包含數據、人物、機構名稱）。
       - 深入的觀點解析與背景補充（IoT 觀點）。
    4. 必須包含關於「為何美國不炸伊朗石油設施」、「蔣介石典故」、「兩會官員失聯」等細節（如果影片中有提到）。
    
    請提供與專業智庫報告同等級別的詳細內容。
    """

    print(f"正在分析最新影片內容，請稍候（這可能需要較長時間以確保品質）...")
    
    final_response = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=deep_prompt,
        config=types.GenerateContentConfig(
            # 這裡不開搜尋，讓它專注於處理第一步找到的影片內容
            temperature=0.2,
            system_instruction="你是一位資深的政經評論員與情報分析官。你的任務是提供極其詳盡、結構嚴謹且富有洞察力的影片總結。"
        )
    )

    return final_response.text

if __name__ == "__main__":
    result = get_high_quality_summary("@ltshijie")
    print("\n--- 高品質深度總結 ---")
    print(result)