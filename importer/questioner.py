from utils import content_utils

from setup import ServiceSetup

import anthropic


class Querioner:

    def __init__(self, proj_setup: ServiceSetup):
        self.proj_setup = proj_setup
        self.chat = None
        self.qa_list = [] # [ (prompt, ans), ....]

    def prepare(self):
        """Override to implement for ai model service."""
        pass

    def close_conversation(self):
        """Override to implement for ai model service."""
        self.conversations = []

    def ask(self, prompt:str, system_role:str=None)->str:
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


class ClaudeQuestioner(Querioner):

    def prepare(self, model="claude-3-5-haiku-20241022"):
        self.model = model
        if self.chat:
            return

        self.chat = anthropic.Anthropic(
            api_key=self.proj_setup.anthropic_key,
        )
        self.qa_list = []

    def close_conversation(self):
        self.qa_list = []

    def ask(self, prompt, system_role=None):
        responses = self.chat.messages.create(
            model=self.model,
            max_tokens=3000,
            temperature=0.0,
            system=system_role,
            messages=self.wrap_conversation(system_role=system_role, next_q=prompt)
        )

        ans = "".join([ chunk.text for chunk in responses.content ])
        self.stash_qa(prompt, ans)
        return ans


class ClaudeSrtSummary(ClaudeQuestioner):

    def __init__(self, proj_setup):
        super().__init__(proj_setup)
        self.init_prompt = "你是世界前500強執行長的的秘書，我將給予讀稿，請從讀稿中，使用繁體中文回覆請求，並且只使用Markdown unordered list '- '格式來進行排版，即便是標題也需要使用 '- '"

    def summarize_srt(self, q, srt_fp, with_ts=False):
        if not srt_fp:
            return
        
        content = None
        if with_ts:
            with open(srt_fp) as src:
                content = src.read()
        else:
            content = content_utils.srt_file_to_txt_content(srt_fp)
        
        # Sent init prompt and content at once, will get better result for lower model.
        
        print("Ask: " + q)
        ans = self.ask(
            "\n".join([q, content]), 
            system_role=self.init_prompt
        )
        print("Ans:" + ans)