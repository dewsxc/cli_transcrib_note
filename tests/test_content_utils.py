# -*- coding: utf-8 -*-
"""SRT normalization tests.

Regression cover for the bug where Gemini returned its own cue style,
"[ 00:00.380 --> 00:05.150 ] text", instead of SRT. normalize_srt recognised
none of those lines, fell through to `if not entries: return srt_content`, and
handed the raw text back unchanged — which then got written out as a .srt file
that was not SRT at all, and read downstream as 0% coverage.
"""
import unittest

from . import _path  # noqa: F401  (sys.path bootstrap)
from utils.content_utils import _fmt_ts, _unwrap_bracketed, normalize_srt


class FormatTimestampTest(unittest.TestCase):

    def test_two_field_mm_ss_mmm(self):
        """Gemini's MM:SS.mmm cue timestamps carry no hour field."""
        self.assertEqual(_fmt_ts('00:05.150'), '00:00:05,150')
        self.assertEqual(_fmt_ts('10:39.360'), '00:10:39,360')
        self.assertEqual(_fmt_ts('26:09.110'), '00:26:09,110')

    def test_two_field_rolls_over_past_an_hour(self):
        self.assertEqual(_fmt_ts('75:04.500'), '01:15:04,500')

    def test_two_field_pads_short_milliseconds(self):
        self.assertEqual(_fmt_ts('01:02.5'), '00:01:02,500')

    def test_compact_three_field_still_works(self):
        """Pre-existing MM:SS:mmm support must not regress."""
        self.assertEqual(_fmt_ts('02:22:450'), '00:02:22,450')

    def test_standard_timestamps_pass_through(self):
        self.assertEqual(_fmt_ts('01:02:03.400'), '01:02:03,400')
        self.assertEqual(_fmt_ts('01:02:03,400'), '01:02:03,400')
        self.assertEqual(_fmt_ts('01:02:03'), '01:02:03,000')


class UnwrapBracketedTest(unittest.TestCase):

    def test_unwraps_a_cue(self):
        self.assertEqual(
            _unwrap_bracketed('[ 00:00.380 --> 00:05.150 ] 第一句話'),
            '00:00.380 --> 00:05.150 第一句話',
        )

    def test_leaves_bracketed_text_alone(self):
        """A bracket without an arrow is subtitle content, not a cue header."""
        for line in ('[音樂]', '[掌聲] 謝謝大家', '[Applause]'):
            self.assertEqual(_unwrap_bracketed(line), line)


class NormalizeSrtGeminiCueStyleTest(unittest.TestCase):
    """The exact shape Gemini returned when this bug was found."""

    RAW = (
        "[ 00:00.380 --> 00:05.150 ] 不廢話，只講乾貨。\n"
        "[ 00:05.340 --> 00:09.130 ] 今天休假看黃金。\n"
        "[ 10:39.360 --> 11:44.560 ] 第十分鐘的內容。"
    )

    def setUp(self):
        self.out = normalize_srt(self.RAW)

    def test_all_cues_are_parsed(self):
        self.assertEqual(self.out.count('-->'), 3)

    def test_emits_standard_srt(self):
        self.assertTrue(self.out.startswith('1\n00:00:00,380 --> 00:00:05,150\n'))

    def test_minutes_do_not_leak_into_the_hour_field(self):
        """The 452%-coverage symptom: 10 minutes rendered as 01:10:39."""
        self.assertIn('00:10:39,360 --> 00:11:44,560', self.out)
        self.assertNotIn('01:10:39', self.out)

    def test_brackets_are_gone(self):
        self.assertNotIn('[', self.out)

    def test_subtitle_text_survives(self):
        self.assertIn('不廢話，只講乾貨。', self.out)
        self.assertIn('第十分鐘的內容。', self.out)


class NormalizeSrtRegressionTest(unittest.TestCase):
    """Loosening the timestamp regex must not disturb formats that already worked."""

    def test_standard_srt_is_idempotent(self):
        srt = ("1\n00:00:01,000 --> 00:00:02,500\n你好\n\n"
               "2\n00:00:02,500 --> 00:00:04,000\n再見\n")
        once = normalize_srt(srt)
        self.assertIn('00:00:01,000 --> 00:00:02,500', once)
        self.assertIn('00:00:02,500 --> 00:00:04,000', once)
        self.assertEqual(once.strip(), normalize_srt(once).strip())

    def test_single_line_with_sequence_number(self):
        self.assertIn(
            '00:00:01,000 --> 00:00:02,000',
            normalize_srt('1 00:00:01,000 --> 00:00:02,000 你好'),
        )

    def test_single_dash_arrow(self):
        self.assertIn(
            '00:00:01,000 --> 00:00:02,000',
            normalize_srt('00:00:01,000 -> 00:00:02,000 你好'),
        )

    def test_unparseable_input_is_returned_unchanged(self):
        junk = '這裡完全沒有時間戳記。'
        self.assertEqual(normalize_srt(junk), junk)


if __name__ == '__main__':
    unittest.main()
