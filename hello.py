from setup import ServiceSetup

import google.generativeai as genai
from importer.questioner import GeminiSrtSummary


setup = ServiceSetup('./resources/config.yml')


def talk_to_gemini(prompt: str, srt_fp: str=None):
    """
    Initializes the Gemini API, loads the Gemini model, and sends a prompt.

    Args:
        prompt (str): The text prompt to send to the Gemini model.
    """
    try:
        genai.configure(api_key=setup.gc_gemini_api_key)
        
        # Define system instruction for the AI's role
        system_instruction = "You are a professional news summarizer. Your role is to analyze news content and provide concise, well-structured summaries in Traditional Chinese using markdown unordered list format. Focus on key points and essential information without unnecessary elaboration."
        
        model = genai.GenerativeModel("gemini-2.5-flash", system_instruction=system_instruction)
        chat = model.start_chat()

        print(f"Sending prompt to Gemini: '{prompt}'")

        content = ""
        if srt_fp:
            with open(srt_fp) as src:
                content = src.read()

        response = chat.send_message(prompt + '\n' + content)
        
        print("\nGemini's response:")
        print(f"Response text: {response.text}")

    except Exception as e:
        print(f"An error occurred: {e}")
        print("Please ensure you have a valid Gemini API key configured.")

# Still need transcript by ourself.
# talk_to_gemini(
#     "請總結讀稿，使用繁體中文回覆請求，並且只使用Markdown unordered list '- '格式來進行排版，即便是標題也需要使用 '- '，請直接列出核心要點、關鍵訊息、無需開場白、避免廢話、不用客套、不用重複命令、不用結語，", 
#     "./tmp/audio/和風書院 - 國際新聞評論 2025 03 18 劉必榮教授一周國際新聞評論 中東戰事再起 中俄伊三國副外長級的會議 俄烏戰爭後續 美國遣返這個拉丁美洲的黑幫.srt",
# )

talk_to_gemini("Hello?")

c = GeminiSrtSummary(setup)
c.summarize_srt("列出所有重要新聞並且摘要文中對新聞的觀點以及敘述", "./tmp/audio/和風書院 - 國際新聞評論 2025 03 18 劉必榮教授一周國際新聞評論 中東戰事再起 中俄伊三國副外長級的會議 俄烏戰爭後續 美國遣返這個拉丁美洲的黑幫.srt", with_ts=True)
