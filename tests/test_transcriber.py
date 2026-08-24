# -*- coding: utf-8 -*-
"""Gemini transcription guard-rail tests.

Covers the three defects found together:

1. Uploads failed outright because the MIME type was guessed from the file
   extension. yt-dlp saves YouTube's HLS audio as .mp4 while the bytes are a raw
   ADTS AAC stream, and Gemini picks its decoder from the MIME's top-level type,
   so an audio-only file announced as video/* goes to the video transcoder and
   comes back FAILED.
2. Coverage was read off the last cue rather than the latest one, so Gemini's
   out-of-order cues under-reported it.
3. The weaker models translate Chinese audio into English instead of
   transcribing it, which used to be written out silently.
"""
import unittest

from . import _path  # noqa: F401  (sys.path bootstrap)
from importer import transcriber
from importer.transcriber import (
    _detect_gemini_mime,
    _get_srt_end_seconds,
    _is_srt_monolithic,
    _is_wrong_language,
)


def _probe(format_name, stream_types=('audio',), attached_pic=False):
    """Build a synthetic ffprobe result so these tests need no media files."""
    streams = []
    for codec_type in stream_types:
        stream = {'codec_type': codec_type}
        if codec_type == 'video' and attached_pic:
            stream['disposition'] = {'attached_pic': 1}
        streams.append(stream)
    return {'format': {'format_name': format_name}, 'streams': streams}


class DetectGeminiMimeTest(unittest.TestCase):

    def setUp(self):
        self._real_ffprobe = transcriber._ffprobe
        self.addCleanup(setattr, transcriber, '_ffprobe', self._real_ffprobe)

    def _probes_as(self, probe):
        transcriber._ffprobe = lambda fp: probe

    def test_hls_audio_saved_as_mp4_is_declared_aac(self):
        """The original failure: .mp4 on disk, raw ADTS AAC inside."""
        self._probes_as(_probe('aac'))
        self.assertEqual(_detect_gemini_mime('whatever.mp4'), 'audio/aac')

    def test_audio_only_mp4_container_is_declared_audio(self):
        """A genuine MP4 container still fails Gemini if announced as video/mp4."""
        self._probes_as(_probe('mov,mp4,m4a,3gp,3g2,mj2'))
        self.assertEqual(_detect_gemini_mime('a.mp4'), 'audio/mp4')

    def test_audio_only_webm_is_declared_audio(self):
        self._probes_as(_probe('matroska,webm'))
        self.assertEqual(_detect_gemini_mime('a.webm'), 'audio/webm')

    def test_other_audio_containers(self):
        for fmt, mime in (('mp3', 'audio/mpeg'), ('wav', 'audio/wav'),
                          ('flac', 'audio/flac'), ('ogg', 'audio/ogg')):
            self._probes_as(_probe(fmt))
            self.assertEqual(_detect_gemini_mime('a.' + fmt), mime)

    def test_real_video_defers_to_the_extension(self):
        """--hd-video downloads must keep working; video/mp4 is right for them."""
        self._probes_as(_probe('mov,mp4,m4a,3gp,3g2,mj2', ('video', 'audio')))
        self.assertIsNone(_detect_gemini_mime('a.mp4'))

    def test_cover_art_does_not_make_a_file_a_video(self):
        self._probes_as(_probe('mov,mp4,m4a,3gp,3g2,mj2', ('video', 'audio'),
                               attached_pic=True))
        self.assertEqual(_detect_gemini_mime('a.m4a'), 'audio/mp4')

    def test_unknown_container_defers_to_the_extension(self):
        self._probes_as(_probe('some-new-format'))
        self.assertIsNone(_detect_gemini_mime('a.xyz'))

    def test_unprobeable_file_defers_to_the_extension(self):
        self._probes_as({})
        self.assertIsNone(_detect_gemini_mime('missing.mp4'))


class SrtEndSecondsTest(unittest.TestCase):

    def test_uses_the_latest_cue_not_the_last_one(self):
        """Gemini emits cues out of order; the last line is not the latest time."""
        srt = ("1\n00:00:10,000 --> 00:01:00,000\nA\n\n"
               "2\n00:00:05,000 --> 00:00:30,000\nB\n")
        self.assertEqual(_get_srt_end_seconds(srt), 60.0)

    def test_reads_milliseconds(self):
        self.assertEqual(
            _get_srt_end_seconds('1\n00:00:00,000 --> 00:00:02,250\nA\n'), 2.25)

    def test_reads_hours(self):
        self.assertEqual(
            _get_srt_end_seconds('1\n00:00:00,000 --> 01:00:00,000\nA\n'), 3600.0)

    def test_unparseable_returns_zero(self):
        self.assertEqual(_get_srt_end_seconds('沒有時間戳記'), 0.0)


class WrongLanguageTest(unittest.TestCase):

    ENGLISH = ("1\n00:00:01,000 --> 00:00:02,000\n"
               "No fluff, just facts, looking at gold today.\n")
    CHINESE = ("1\n00:00:01,000 --> 00:00:02,000\n"
               "沒有廢話，只有事實，今天來看黃金。\n")

    def test_translated_output_is_caught(self):
        self.assertTrue(_is_wrong_language(self.ENGLISH, 'zh'))

    def test_chinese_output_passes(self):
        self.assertFalse(_is_wrong_language(self.CHINESE, 'zh'))

    def test_chinese_variants_are_checked_too(self):
        for lang in ('zh-TW', 'zh-CN', 'zh-Hant', 'ZH'):
            self.assertTrue(_is_wrong_language(self.ENGLISH, lang), lang)

    def test_english_channels_are_not_flagged(self):
        self.assertFalse(_is_wrong_language(self.ENGLISH, 'en'))

    def test_embedded_latin_terms_do_not_trip_it(self):
        """Chinese finance transcripts are full of tickers and acronyms."""
        srt = ("1\n00:00:01,000 --> 00:00:02,000\n"
               "美股 ETF 上漲，Fed 決議公布後 GDP 數據轉強。\n")
        self.assertFalse(_is_wrong_language(srt, 'zh'))

    def test_timestamps_are_not_counted_as_text(self):
        """Digits and arrows must not sway the CJK-vs-Latin ratio."""
        srt = "\n\n".join(
            f"{i}\n00:00:{i:02d},000 --> 00:00:{i + 1:02d},000\n短句。"
            for i in range(1, 30))
        self.assertFalse(_is_wrong_language(srt, 'zh'))


class MonolithicSrtTest(unittest.TestCase):

    def test_one_cue_for_a_long_recording_is_monolithic(self):
        srt = '1\n00:00:00,000 --> 00:20:00,000\n很長的一段話。\n'
        self.assertTrue(_is_srt_monolithic(srt, 1200))

    def test_normally_segmented_srt_is_not(self):
        srt = "\n\n".join(
            f"{i}\n00:00:{i:02d},000 --> 00:00:{i + 1:02d},000\n短句。"
            for i in range(1, 60))
        self.assertFalse(_is_srt_monolithic(srt, 1200))


if __name__ == '__main__':
    unittest.main()
