import re
import os

from zhconv import convert


# ===== Format =====


# Timestamp: HH:MM:SS,mmm  or  HH:MM:SS.mmm  or  HH:MM:SS  (no ms)
# Also handles Gemini's compact MM:SS:mmm format (e.g. 02:22:450) and its
# two-field MM:SS.mmm format (e.g. 10:39.360). Three-field alternatives must
# stay first so they win over the two-field one on an ambiguous prefix.
_TS = r'(?:\d{1,2}:\d{2}:\d{3}|\d{2}:\d{2}:\d{2}(?:[,\.]\d+)?|\d{1,2}:\d{2}[,\.]\d{1,3})'

# Line-level patterns tried in order (most specific first)
# --?> matches both standard --> and Gemini's single-dash ->
_P_SEQ_TS_ARR_TS_TXT = re.compile(r'^(\d+)\s+(' + _TS + r')\s*--?>\s*(' + _TS + r')\s+(.+)$')
_P_TS_ARR_TS_TXT     = re.compile(r'^(' + _TS + r')\s*--?>\s*(' + _TS + r')\s+(.+)$')
_P_TS_ARR_TS         = re.compile(r'^(' + _TS + r')\s*--?>\s*(' + _TS + r')\s*$')
_P_SEQ_TS_TS_TXT     = re.compile(r'^(\d+)\s+(' + _TS + r')\s+(' + _TS + r')\s+(.+)$')
_P_SEQ_TS_TS         = re.compile(r'^(\d+)\s+(' + _TS + r')\s+(' + _TS + r')\s*$')
_P_TS_TS_TXT         = re.compile(r'^(' + _TS + r')\s+(' + _TS + r')\s+(.+)$')
_P_TS_TS             = re.compile(r'^(' + _TS + r')\s+(' + _TS + r')\s*$')
_P_SEQ_ONLY          = re.compile(r'^\d+$')


def _fmt_ts(ts: str) -> str:
    ts = ts.strip()
    # Gemini compact format: MM:SS:mmm (e.g. 02:22:450) → HH:MM:SS,mmm
    m = re.match(r'^(\d{1,2}):(\d{2}):(\d{3})$', ts)
    if m:
        total_mm, ss, mmm = int(m.group(1)), int(m.group(2)), m.group(3)
        hh, mm = divmod(total_mm, 60)
        return f'{hh:02d}:{mm:02d}:{ss:02d},{mmm}'
    # Gemini two-field format: MM:SS.mmm (e.g. 10:39.360) → HH:MM:SS,mmm
    m = re.match(r'^(\d{1,2}):(\d{2})[,\.](\d{1,3})$', ts)
    if m:
        total_mm, ss, mmm = int(m.group(1)), int(m.group(2)), m.group(3).ljust(3, '0')
        hh, mm = divmod(total_mm, 60)
        return f'{hh:02d}:{mm:02d}:{ss:02d},{mmm}'
    ts = ts.replace('.', ',')
    if not re.search(r',\d+$', ts):
        ts += ',000'
    return ts


# Gemini also wraps each cue as "[ ts --> ts ] text" instead of emitting SRT.
_P_BRACKETED = re.compile(r'^\[\s*(.+?)\s*\]\s*(.*)$')


def _unwrap_bracketed(line: str) -> str:
    """Turn Gemini's "[ ts --> ts ] text" cue style into a plain "ts --> ts text" line."""
    m = _P_BRACKETED.match(line)
    if m and '->' in m.group(1):
        return f'{m.group(1)} {m.group(2)}'.strip()
    return line


def _is_structural(line: str) -> bool:
    """True if line is a timestamp or pure sequence number (not subtitle text)."""
    return bool(
        _P_SEQ_ONLY.match(line) or
        _P_TS_ARR_TS.match(line) or
        _P_TS_TS.match(line) or
        _P_SEQ_TS_TS.match(line)
    )


def normalize_srt(srt_content):
    """Normalize non-standard SRT variants to standard multi-line format.

    Handles:
    - seq ts --> ts text  (single-line, with arrow)
    - seq ts ts text      (single-line, no arrow, e.g. MM:SS:cs MM:SS:cs)
    - ts --> ts \\n text   (two-line, no seq)
    - ts ts \\n text       (two-line, no arrow, no seq)
    - Already-standard format is re-emitted unchanged in structure.
    """
    lines = srt_content.split('\n')
    entries = []  # (ts1, ts2, text)
    i = 0

    while i < len(lines):
        line = _unwrap_bracketed(lines[i].strip())

        m = _P_SEQ_TS_ARR_TS_TXT.match(line)
        if m:
            entries.append((_fmt_ts(m.group(2)), _fmt_ts(m.group(3)), m.group(4)))
            i += 1; continue

        m = _P_TS_ARR_TS_TXT.match(line)
        if m:
            entries.append((_fmt_ts(m.group(1)), _fmt_ts(m.group(2)), m.group(3)))
            i += 1; continue

        m = _P_TS_ARR_TS.match(line)
        if m:
            ts1, ts2 = _fmt_ts(m.group(1)), _fmt_ts(m.group(2))
            i += 1
            while i < len(lines) and not lines[i].strip():
                i += 1
            if i < len(lines):
                nxt = lines[i].strip()
                if nxt and not _is_structural(nxt):
                    entries.append((ts1, ts2, nxt)); i += 1; continue
            entries.append((ts1, ts2, '')); continue

        m = _P_SEQ_TS_TS_TXT.match(line)
        if m:
            entries.append((_fmt_ts(m.group(2)), _fmt_ts(m.group(3)), m.group(4)))
            i += 1; continue

        m = _P_SEQ_TS_TS.match(line)
        if m:
            ts1, ts2 = _fmt_ts(m.group(2)), _fmt_ts(m.group(3))
            i += 1
            while i < len(lines) and not lines[i].strip():
                i += 1
            if i < len(lines):
                nxt = lines[i].strip()
                if nxt and not _is_structural(nxt):
                    entries.append((ts1, ts2, nxt)); i += 1; continue
            entries.append((ts1, ts2, '')); continue

        m = _P_TS_TS_TXT.match(line)
        if m:
            entries.append((_fmt_ts(m.group(1)), _fmt_ts(m.group(2)), m.group(3)))
            i += 1; continue

        m = _P_TS_TS.match(line)
        if m:
            ts1, ts2 = _fmt_ts(m.group(1)), _fmt_ts(m.group(2))
            i += 1
            while i < len(lines) and not lines[i].strip():
                i += 1
            if i < len(lines):
                nxt = lines[i].strip()
                if nxt and not _is_structural(nxt):
                    entries.append((ts1, ts2, nxt)); i += 1; continue
            entries.append((ts1, ts2, '')); continue

        i += 1  # skip empty lines, pure seq numbers, unrecognized lines

    if not entries:
        return srt_content

    result = []
    for seq, (ts1, ts2, text) in enumerate(entries, 1):
        result.append(str(seq))
        result.append(f'{ts1} --> {ts2}')
        result.append(text)
        result.append('')
    return '\n'.join(result)


_VTT_CUE = re.compile(
    r'^(\d{2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[.,]\d{3})')
_VTT_TAG = re.compile(r'<[^>]+>')                       # <c>, </c>, <00:00:01.000>, etc.
_VTT_INLINE_TS = re.compile(r'<\d{2}:\d{2}:\d{2}[.,]\d{3}>')


def vtt_to_srt(vtt_content):
    """Convert WebVTT (incl. YouTube auto-caption VTT) to SRT text.

    YouTube auto-captions use a rolling format where each cue repeats the
    previously shown line and reveals the next line with inline word-level
    <hh:mm:ss.mmm><c> ... </c> timing tags. We keep, per cue, the line that
    carries those inline tags (the freshly spoken words) and drop the repeated
    lines, then collapse consecutive identical lines. Manually-uploaded VTT
    (no inline tags) just falls back to its last line, so it converts cleanly
    too.
    """
    lines = vtt_content.split('\n')
    entries = []  # (start, end, text)
    i, n = 0, len(lines)

    while i < n:
        m = _VTT_CUE.match(lines[i].strip())
        if not m:
            i += 1
            continue
        start, end = m.group(1), m.group(2)
        i += 1

        # Collect this cue's text until the next cue, skipping blank/separator
        # lines (YouTube sometimes injects whitespace-only lines mid-cue).
        text_lines = []
        while i < n and not _VTT_CUE.match(lines[i].strip()):
            if lines[i].strip():
                text_lines.append(lines[i])
            i += 1

        # Lines carrying inline timing are the freshly-spoken words; if none,
        # keep only the last line (the most recently revealed one).
        timed = [l for l in text_lines if _VTT_INLINE_TS.search(l)]
        candidate_lines = timed if timed else text_lines[-1:]

        text = ' '.join(_VTT_TAG.sub('', l).strip() for l in candidate_lines if l.strip())
        text = re.sub(r'\s+', ' ', text).strip()
        if text:
            entries.append((start.replace('.', ','), end.replace('.', ','), text))

    # Collapse consecutive duplicate lines, extending the end timestamp.
    deduped = []
    for s, e, t in entries:
        if deduped and deduped[-1][2] == t:
            deduped[-1] = (deduped[-1][0], e, t)
        else:
            deduped.append((s, e, t))

    out = []
    for idx, (s, e, t) in enumerate(deduped, 1):
        out.extend([str(idx), f'{s} --> {e}', t, ''])
    return '\n'.join(out)


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
        next_is_text = False
        for l in src.readlines():
            raw = l.strip()
            if raw == "":
                continue
            if '-->' in raw:
                if save_start_ts:
                    m = re.search(r"[\d:,\.]+", raw)
                    start_ts = m.group(0) if m else None
                next_is_text = True
            elif next_is_text:
                if save_start_ts and start_ts:
                    dst.write("- {} {}\n".format(start_ts, raw))
                else:
                    dst.write("- {}\n".format(raw))
                next_is_text = False

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

