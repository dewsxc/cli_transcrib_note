import os
from pathlib import Path
from datetime import datetime

from utils import file_utils
from setup import ServiceSetup
from utils import content_utils


class MarkDownHelper:

    @classmethod
    def compose_summarize_md(cls, title, summerize):
        return "\n- " + title + "\n" + "\t- " + summerize
    
    @classmethod
    def compose_file_link(cls, fn):
        return "[[{}]]".format(fn)
    
    @classmethod
    def compose_page_link(cls, page, fn):
        return "[[{}/{}]]".format(page, fn)
    
    @classmethod
    def compose_page_video_link_md(cls, page, fn, link):
        return "[[{}/{}]] - [Link]({})".format(page, fn, link)
    
    @classmethod
    def compose_summarize_from_qa_lsit_md(cls, qa_list, save_ans_only=True):
        md_items = []

        for q, a in qa_list:
            if not save_ans_only:
                md_items.append("\n\t- {}".format(q))
            
            ans = '\n'.join([ '\t{}'.format('' if save_ans_only else '\t') + l for l in a.split('\n') ])
            md_items.append(ans)
        
        return "\n".join(md_items)


"""
1. Save summary to journal, save file to daily folder.
    a. News
    b. No topic.
2. Save summary to page, save file to page folder.
"""

class LogseqHelper:

    PAGES_DIR = "pages"
    TRANSCRIPTIONS_DIR = "transcriptions"
    JOURNALS_DIR = "journals"
    
    def __init__(self, proj_setup:ServiceSetup):
        self.proj_setup = proj_setup
    
    def page_fp(self, page):
        return os.path.join(
            self.proj_setup.graph_dir, 
            self.PAGES_DIR, page + ".md"
        )
    
    def transcription_page_fp(self, page, fp):
        return os.path.join(
            self.proj_setup.graph_dir,
            self.TRANSCRIPTIONS_DIR,
            page,
            self.compose_fn_under_page(page, Path(fp).with_suffix("").name),
        )
    
    def diary_transcription_fp(self, fp):
        return os.path.join(
            self.proj_setup.graph_dir,
            self.TRANSCRIPTIONS_DIR,
            datetime.today().strftime("%Y_%m_%d"),
            Path(fp).with_suffix("").name + ".md",
        )
    
    def daily_journal_fp(self):
        return os.path.join(
            self.proj_setup.graph_dir,
            self.JOURNALS_DIR,
            datetime.today().strftime("%Y_%m_%d") + ".md",
        )
    
    def save_under_page(self, sum, page, srt_fp):
        """
        Compose title by use case, not here.
        File: transcriptions/PageName/PageName___FileName.md
        """
        page_fp = self.page_fp(page)
        file_utils.make_dirs_for_fp(page_fp)

        with open(page_fp, 'a') as src:
            src.write("\n")
            src.write(sum)
        print("Save summary to: " + page_fp)

        md_fp = self.transcription_page_fp(page, srt_fp)
        file_utils.make_dirs_for_fp(md_fp)

        content_utils.srt_to_md_list(srt_fp, md_fp)
        print("Saved: " + md_fp)

    def save_under_diary(self, sum, srt_fp):
        """
        File: transcriptions/2021_01_01/FileName.md
        """
        journal_fp = self.daily_journal_fp()
        file_utils.make_dirs_for_fp(journal_fp)

        with open(journal_fp, 'a') as src:
            src.write('\n')
            src.write(sum)
        print("Save summary to: " + journal_fp)

        md_fp = self.diary_transcription_fp(srt_fp)
        file_utils.make_dirs_for_fp(md_fp)

        content_utils.srt_to_md_list(srt_fp, md_fp)
        print("Saved to: " + md_fp)

    @classmethod
    def compose_fn_under_page(cls, page, fn):
        return "{}___{}".format(page, fn) + '.md'