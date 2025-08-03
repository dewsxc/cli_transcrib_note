from utils import content_utils

from setup import ServiceSetup

import anthropic
import google.generativeai as genai


"""
Utils
"""

def get_srt_summarist(args, proj_setup):
    models_map = {
        "gemini-2.5-flash": GeminiQuestioner,
        "claude-3-haiku-20240307": ClaudeQuestioner, 
        "claude-3-5-haiku-20241022": ClaudeQuestioner, 
        "claude-3-5-sonnet-20241022": ClaudeQuestioner,
    } 

    return models_map[args.ai_model](proj_setup, args.ai_model)


class Querioner:

    def __init__(self, proj_setup: ServiceSetup, model=None):
        self.proj_setup = proj_setup
        self.model = model
        self.chat = None
        self.qa_list = [] # [ (prompt, ans), ....]

    def prepare(self):
        """Override to implement for ai model service."""
        if self.chat:
            return
        if not self.model:
            raise Exception("Empty model, please check again.")
        self.qa_list = []

    def close_conversation(self):
        """Override to implement for ai model service."""
        self.qa_list = []

    def ask(self, prompt:str)->str:
        """Override to implement for ai model service."""
        return ""

    def stash_qa(self, q, a):
        self.qa_list.append((q, a))

    def wrap_conversation(self, next_q=None):
        conversation = []
        for q, a in self.qa_list:
            conversation.append({"role": "user", "content": q})
            conversation.append({"role": "assistant", "content": a})
        if next_q:
            conversation.append({"role": "user", "content": next_q})
        return conversation

    def summarize_srt(self, q, srt_fp, with_ts=False):
        """Override to implement for ai model service."""
        pass


class ClaudeQuestioner(Querioner):

    def __init__(self, proj_setup, model="claude-3-5-haiku-20241022"):
        super().__init__(proj_setup, model=model)
        self.init_prompt = "請總結讀稿、使用繁體中文回覆請求，並且只使用Markdown unordered list '- '格式來進行排版，即便是標題也需要使用 '- '，請直接列出核心要點、關鍵訊息、無需開場白、避免廢話、不用客套、不用重複命令、不用結語："

    def prepare(self):
        super().prepare()

        self.chat = anthropic.Anthropic(
            api_key=self.proj_setup.anthropic_key,
        )

    def ask(self, prompt):
        responses = self.chat.messages.create(
            model=self.model,
            max_tokens=3000,
            temperature=0.0,
            system=self.init_prompt,
            messages=self.wrap_conversation(next_q=prompt)
        )

        ans = "".join([ chunk.text for chunk in responses.content ])
        self.stash_qa(prompt, ans)
        return ans

    def summarize_srt(self, q, srt_fp, with_ts=False):
        if not srt_fp:
            return
        
        content = None
        if with_ts:
            with open(srt_fp) as src:
                content = src.read()
        else:
            content = content_utils.srt_file_to_txt_content(srt_fp)
                
        print("Ask: " + q)
        ans = self.ask(
            "\n".join([q, content]), 
            system_role=self.init_prompt
        )
        print("Ans:" + ans)


class GeminiQuestioner(Querioner):

    def __init__(self, proj_setup, model="gemini-2.5-flash"):
        super().__init__(proj_setup, model=model)
        self.init_prompt = "請總結讀稿、使用繁體中文回覆請求，並且只使用Markdown unordered list '- '格式來進行排版，即便是標題也需要使用 '- '，請直接列出核心要點、關鍵訊息、無需開場白、避免廢話、不用客套、不用重複命令、不用結語，"
    
    def prepare(self):
        super().prepare()
        
        genai.configure(api_key=self.proj_setup.gc_gemini_api_key)
        self.chat = genai.GenerativeModel(self.model, system_instruction=self.init_prompt).start_chat()

    def ask(self, prompt):
        responses = self.chat.send_message(prompt)
        ans = responses.text
        self.stash_qa(prompt, ans)
        return ans

    def summarize_srt(self, q, srt_fp, with_ts=False):
        if not srt_fp:
            return
        
        content = None
        if with_ts:
            with open(srt_fp) as src:
                content = src.read()
        else:
            content = content_utils.srt_file_to_txt_content(srt_fp)
        
        print("Ask: " + q)
        ans = self.ask(
            "\n".join([q, content])
        )
        print("Ans:" + ans)
