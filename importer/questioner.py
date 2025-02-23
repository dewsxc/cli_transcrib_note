from utils import content_utils
import anthropic


class Querioner:

    def __init__(self):
        self.chat = None
        self.qa_list = []

    def prepare_chat(self):
        pass

    def close_chat(self):
        pass

    def ask(self, prompt:str)->str:
        return ""

    def stash_qa(self, q, a):
        self.qa_list.append((q, a))

    def ask_and_save(self, question):
        ans = self.ask(question)
        self.stash_qa(question, ans)
        return ans


class ClaudeQuerioner(Querioner):

    def __init__(self, key, model="claude-3-haiku-20240307"):
        super().__init__()
        self.key = key
        self.model = model

    def prepare_chat(self):
        if self.chat:
            return

        self.chat = anthropic.Anthropic(
            api_key=self.key,
        )

    def close_chat(self):
        self.chat = None

    def ask(self, content):
        responses = self.chat.messages.create(
            model=self.model,
            max_tokens=1000,
            temperature=0.0,
            messages=[
                {"role": "user", "content": content}
            ]
        )

        text_response = [ chunk.text for chunk in responses.content ]
        return "".join(text_response)


class ClaudeSrtSummary(ClaudeQuerioner):

    def __init__(self, key, model="claude-3-haiku-20240307"):
        super().__init__(key, model)
        self.init_prompt = "我將上傳讀稿，請從讀稿中，使用繁體中文回覆以下請求，並且只使用Markdown unordered list '- '格式來進行排版，即便是標題也需要使用 '- '"
        self.content = None

    def prepare_chat(self):
        super().prepare_chat()
        self.ask(self.init_prompt)
    
    def summarize_srt(self, q, srt_fp, with_ts=False):
        if not srt_fp:
            return
        if with_ts and srt_fp.endswith(".srt"):
            self.content = content_utils.srt_file_to_txt_content(srt_fp)
        else:
            with open(srt_fp) as src:
                self.content = src.read()
        
        prompt = q + '\n' + self.content
        ans = self.ask_and_save(prompt)

        print("Question: " + q)
        print("Ans:" + ans)
        

