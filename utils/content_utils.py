import re
import os

from zhconv import convert


# ===== Format =====


def srt_to_txt(srt_fp, txt_fp, save_start_ts=False):
    """
    Use srt can split sentence by transcript, that make txt more readable.
    """
    with open(srt_fp, 'r') as src, open(txt_fp, 'w') as dst:
        start_ts = None
        count = 0
        for l in src.readlines():
            raw = l.strip()
            if raw == "":
                count = 0

            elif count == 0: # idx
                count += 1

            elif count == 1: # ts
                if save_start_ts:
                    start_ts = re.findall(r"\d{2}\:\d{2}\:\d{2}", raw)[0]
                count += 1

            elif count == 2: # line
                if save_start_ts:
                    dst.write("{} {}\n".format(start_ts, raw))
                else:
                    dst.write("{}\n".format(raw))
                count = 0
    return True


def srt_file_to_txt_content(srt_fp):
    """
    Use srt can split sentence by transcript, that make txt more readable.
    """
    content = []
    with open(srt_fp, 'r') as src:
        count = 0
        for l in src.readlines():
            raw = l.strip()
            if raw == "":
                count = 0

            elif count == 0: # idx
                count += 1

            elif count == 1: # ts
                count += 1

            elif count == 2: # line
                content.append(raw)
                count = 0

    return "\n".join(content)


def srt_to_md_list(srt_fp, md_fp, save_start_ts=False):
    """
    If import txt into Logseq, that will be only 1 list item and include all content.
    Transform into markdown list format for each line will be easier to editting
    Don't need to feed AI so won't save txt.
    """
    with open(srt_fp, 'r') as src, open(md_fp, 'w') as dst:
        start_ts = None
        count = 0
        for l in src.readlines():
            raw = l.strip()
            if raw == "":
                count = 0

            elif count == 0: # idx
                count += 1

            elif count == 1: # ts
                if save_start_ts:
                    start_ts = re.findall(r"\d{2}\:\d{2}\:\d{2}", raw)[0]
                count += 1

            elif count == 2: # line
                if save_start_ts:
                    dst.write("- {} {}\n".format(start_ts, raw))
                else:
                    dst.write("- {}\n".format(raw))
                count = 0

    return True


# ===== Translate =====

def s_to_t(src_fp):
    """
    For small file, need refactoring if deal with large file.
    Save to tmp, replace original file after convertion.
    """
    if not src_fp:
        return False
    dst_fp = src_fp + ".tmp"

    try:
        with open(src_fp, 'r') as src, open(dst_fp, 'w') as dst:
            dst.write(convert(src.read(), 'zh-tw'))

    except Exception as e:
        print(e)
        if os.path.exists(dst_fp):
            os.remove(dst_fp)  # If error again, it must be bigger problem.
        return False
    
    os.remove(src_fp)
    os.rename(dst_fp, src_fp)

    return True

