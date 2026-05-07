import time
import os
import yaml


def _load_pricing(pricing_yml=None):
    if not pricing_yml:
        pricing_yml = os.path.join(os.path.dirname(__file__), '..', 'resources', 'pricing.yml')
    pricing_yml = os.path.abspath(pricing_yml)
    if not os.path.exists(pricing_yml):
        return {}
    with open(pricing_yml, encoding='utf-8') as f:
        data = yaml.safe_load(f)
    flat = {}
    for provider_models in data.values():
        if isinstance(provider_models, dict):
            for model, prices in provider_models.items():
                if isinstance(prices, dict):
                    flat[model] = {
                        'input': float(prices.get('input', 0)) / 1e6,
                        'output': float(prices.get('output', 0)) / 1e6,
                    }
    return flat


def _fmt_duration(seconds):
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def _fmt_tokens(n):
    return f"{n:,}"


class StatsCollector:

    def __init__(self, pricing_yml=None):
        self._pricing = _load_pricing(pricing_yml)
        self._session_start = time.time()

        # current item accumulators (reset per item)
        self._item_label = None
        self._item_start = None
        self._item_stt = []   # list of stt stat dicts
        self._item_ai = []    # list of ai stat dicts

        # session-level totals
        self._session_items = 0
        self._session_total_duration = 0.0
        self._session_stt = []
        self._session_ai = []

    # ------------------------------------------------------------------ #
    # Item lifecycle
    # ------------------------------------------------------------------ #

    def begin_item(self, label: str):
        self._item_label = label
        self._item_start = time.time()
        self._item_stt = []
        self._item_ai = []

    def end_item(self):
        duration = time.time() - (self._item_start or time.time())
        self._session_items += 1
        self._session_total_duration += duration
        self._session_stt.extend(self._item_stt)
        self._session_ai.extend(self._item_ai)
        return duration

    # ------------------------------------------------------------------ #
    # Recording
    # ------------------------------------------------------------------ #

    def record_stt(self, backend, audio_duration, proc_time, model=None, in_tokens=0, out_tokens=0, retry_time=0.0, retry_count=0, retry_in_tokens=0, retry_out_tokens=0):
        cost = self._calc_cost(model, in_tokens, out_tokens) if model else 0.0
        retry_cost = self._calc_cost(model, retry_in_tokens, retry_out_tokens) if model else 0.0
        self._item_stt.append({
            'backend': backend,
            'model': model,
            'audio_duration': audio_duration,
            'proc_time': proc_time,
            'retry_time': retry_time,
            'retry_count': retry_count,
            'retry_in_tokens': retry_in_tokens,
            'retry_out_tokens': retry_out_tokens,
            'retry_cost': retry_cost,
            'in_tokens': in_tokens,
            'out_tokens': out_tokens,
            'cost': cost,
        })

    def record_ai(self, model, in_tokens, out_tokens):
        cost = self._calc_cost(model, in_tokens, out_tokens)
        self._item_ai.append({
            'model': model,
            'in_tokens': in_tokens,
            'out_tokens': out_tokens,
            'cost': cost,
        })

    # ------------------------------------------------------------------ #
    # Printing
    # ------------------------------------------------------------------ #

    def print_item_stats(self):
        duration = time.time() - (self._item_start or time.time())
        label = self._item_label or ''
        item_cost = sum(r['cost'] for r in self._item_stt + self._item_ai)

        lines = [f"\n--- 項目統計 [{label}] ---"]
        lines.append(f"處理時間: {_fmt_duration(duration)}")

        for r in self._item_stt:
            ratio = r['audio_duration'] / r['proc_time'] if r['proc_time'] > 0 else 0
            tag = r['model'] or r['backend']
            lines.append(f"\nSpeech-to-Text ({tag}):")
            lines.append(f"  音訊時長: {_fmt_duration(r['audio_duration'])} / 轉錄耗時: {_fmt_duration(r['proc_time'])} / 速率: {ratio:.1f}x")
            if r.get('retry_count', 0) > 0:
                lines.append(f"  重試: {r['retry_count']} 次 / 重試耗時: {_fmt_duration(r['retry_time'])}")
                lines.append(f"  重試 Tokens: {_fmt_tokens(r['retry_in_tokens'])} 輸入 / {_fmt_tokens(r['retry_out_tokens'])} 輸出 / 成本: ${r['retry_cost']:.4f} USD")
            if r['in_tokens'] or r['out_tokens']:
                lines.append(f"  Tokens: {_fmt_tokens(r['in_tokens'])} 輸入 / {_fmt_tokens(r['out_tokens'])} 輸出")
                lines.append(f"  成本: ${r['cost']:.4f} USD")

        for r in self._item_ai:
            lines.append(f"\nAI 摘要 ({r['model']}):")
            lines.append(f"  Tokens: {_fmt_tokens(r['in_tokens'])} 輸入 / {_fmt_tokens(r['out_tokens'])} 輸出")
            lines.append(f"  成本: ${r['cost']:.4f} USD")

        if item_cost > 0:
            lines.append(f"\n本項目成本: ${item_cost:.4f} USD")

        print('\n'.join(lines))

    def print_session_stats(self):
        if self._session_items == 0:
            return

        avg = self._session_total_duration / self._session_items
        session_cost = sum(r['cost'] for r in self._session_stt + self._session_ai)

        lines = ["\n===== 執行統計總覽 ====="]
        lines.append(f"總項目數: {self._session_items} / 總耗時: {_fmt_duration(self._session_total_duration)} / 平均: {_fmt_duration(avg)}")

        # Aggregate STT by backend/model
        stt_groups = {}
        for r in self._session_stt:
            key = r['model'] or r['backend']
            if key not in stt_groups:
                stt_groups[key] = {'audio': 0.0, 'proc': 0.0, 'retry': 0.0, 'retry_count': 0, 'retry_in': 0, 'retry_out': 0, 'retry_cost': 0.0, 'in': 0, 'out': 0, 'cost': 0.0}
            stt_groups[key]['audio'] += r['audio_duration']
            stt_groups[key]['proc'] += r['proc_time']
            stt_groups[key]['retry'] += r.get('retry_time', 0)
            stt_groups[key]['retry_count'] += r.get('retry_count', 0)
            stt_groups[key]['retry_in'] += r.get('retry_in_tokens', 0)
            stt_groups[key]['retry_out'] += r.get('retry_out_tokens', 0)
            stt_groups[key]['retry_cost'] += r.get('retry_cost', 0.0)
            stt_groups[key]['in'] += r['in_tokens']
            stt_groups[key]['out'] += r['out_tokens']
            stt_groups[key]['cost'] += r['cost']

        for key, g in stt_groups.items():
            ratio = g['audio'] / g['proc'] if g['proc'] > 0 else 0
            lines.append(f"\nSTT 總計 ({key}):")
            lines.append(f"  總音訊: {_fmt_duration(g['audio'])} / 轉錄耗時: {_fmt_duration(g['proc'])} / 平均速率: {ratio:.1f}x")
            if g['retry_count'] > 0:
                lines.append(f"  總重試: {g['retry_count']} 次 / 重試耗時: {_fmt_duration(g['retry'])}")
                lines.append(f"  重試 Tokens: {_fmt_tokens(g['retry_in'])} in / {_fmt_tokens(g['retry_out'])} out / 成本: ${g['retry_cost']:.4f}")
            if g['in'] or g['out']:
                lines.append(f"  Tokens: {_fmt_tokens(g['in'])} in / {_fmt_tokens(g['out'])} out / 成本: ${g['cost']:.4f}")

        # Aggregate AI by model
        ai_groups = {}
        for r in self._session_ai:
            key = r['model']
            if key not in ai_groups:
                ai_groups[key] = {'in': 0, 'out': 0, 'cost': 0.0}
            ai_groups[key]['in'] += r['in_tokens']
            ai_groups[key]['out'] += r['out_tokens']
            ai_groups[key]['cost'] += r['cost']

        for key, g in ai_groups.items():
            lines.append(f"\nAI 摘要總計 ({key}):")
            lines.append(f"  Tokens: {_fmt_tokens(g['in'])} in / {_fmt_tokens(g['out'])} out / 成本: ${g['cost']:.4f}")

        if session_cost > 0:
            lines.append(f"\n總成本: ${session_cost:.4f} USD")

        lines.append("=========================")
        print('\n'.join(lines))

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _calc_cost(self, model, in_tokens, out_tokens):
        prices = self._pricing.get(model)
        if not prices:
            return 0.0
        return in_tokens * prices['input'] + out_tokens * prices['output']
