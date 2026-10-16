"""每句 take：whisper 转写 + 强制解码打分，挑最清楚的一条，复制到 audio/lines/sNN.mp3。

python3.12 asr_pick.py [3,7]   （只重挑这几句）→ asr_takes.json、picks.json、audio/lines/
需要 openai-whisper、torch、pypinyin；第一次会下载 large-v3-turbo 和 medium 两个模型。

排序依据：
1. 无调拼音字错率（转写 vs 台本）——同音字不算错，平翘舌、前后鼻音算错；
2. 强制解码 log P(台本 | 音频)，越高说明音频越像台本（与语言偏好无关，因为同一段文字只比音频）。
两个模型（turbo + medium）各算一遍取和。
"""
import json
import re
import shutil
import sys
from pathlib import Path

import numpy as np
import torch
import whisper
from pypinyin import lazy_pinyin

WORK = Path(__file__).resolve().parent
AUDIO = WORK.parent / "audio"
sys.path.insert(0, str(WORK))
from episode import SENTENCES  # noqa: E402

DIGITS = "零一二三四五六七八九"
PUNCT = re.compile(r"[，。、！？：；,.!?:;\s\"“”‘’'（）()]")


def num_words(n):
    n = int(n)
    if n < 10:
        return DIGITS[n]
    tens, ones = divmod(n, 10)
    return ("" if tens == 1 else DIGITS[tens]) + "十" + (DIGITS[ones] if ones else "")


def normalize(text):
    text = re.sub(r"(\d+)%\s*[-~～至到]\s*(\d+)%", lambda m: f"百分之{num_words(m[1])}到{num_words(m[2])}", text)
    text = re.sub(r"(\d+)\s*[-~～至到]\s*(\d+)%", lambda m: f"百分之{num_words(m[1])}到{num_words(m[2])}", text)
    text = re.sub(r"(\d+)%", lambda m: f"百分之{num_words(m[1])}", text)
    return PUNCT.sub("", text)


def edit_distance(a, b):
    d = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        prev, d[0] = d[0], i
        for j, y in enumerate(b, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (x != y))
    return d[len(b)]


def pinyin_cer(ref, hyp):
    r, h = lazy_pinyin(normalize(ref)), lazy_pinyin(normalize(hyp))
    return edit_distance(r, h) / max(1, len(r))


class Scorer:
    def __init__(self, name):
        self.m = whisper.load_model(name)
        self.tok = whisper.tokenizer.get_tokenizer(self.m.is_multilingual, num_languages=self.m.num_languages,
                                                   language="zh", task="transcribe")
        self.sot = list(self.tok.sot_sequence_including_notimestamps)

    def transcribe(self, path):
        r = self.m.transcribe(str(path), language="zh", word_timestamps=True,
                              initial_prompt="以下是普通话的句子。")
        words = [dict(w=w["word"], s=round(w["start"], 3), e=round(w["end"], 3))
                 for seg in r["segments"] for w in seg["words"]]
        return r["text"], words

    def logp(self, path, text):
        audio = whisper.pad_or_trim(whisper.load_audio(str(path)))
        mel = whisper.log_mel_spectrogram(audio, n_mels=self.m.dims.n_mels).to(self.m.device)
        toks = self.sot + self.tok.encode(text) + [self.tok.eot]
        x = torch.tensor([toks], device=self.m.device)
        with torch.no_grad():
            feats = self.m.embed_audio(mel[None])
            lp = torch.log_softmax(self.m.logits(x[:, :-1], feats).float(), -1)
        return float(lp.gather(-1, x[:, 1:, None]).squeeze(-1)[0][len(self.sot) - 1:].sum())


def main():
    only = {int(x) for x in sys.argv[1].split(",")} if len(sys.argv) > 1 else None
    todo = [s for s in SENTENCES if only is None or s["id"] in only]
    takes = {s["id"]: sorted((AUDIO / "takes").glob(f"s{s['id']:02d}_t*.mp3")) for s in todo}
    old_report = json.loads((WORK / "asr_takes.json").read_text()) if (WORK / "asr_takes.json").exists() else {}
    old_picks = json.loads((WORK / "picks.json").read_text()) if (WORK / "picks.json").exists() else {}
    report = {s["id"]: {p.name: {} for p in takes[s["id"]]} for s in todo}
    for name in ("large-v3-turbo", "medium"):
        sc = Scorer(name)
        for s in todo:
            for p in takes[s["id"]]:
                hyp, words = sc.transcribe(p)
                report[s["id"]][p.name][name] = dict(hyp=hyp, cer=round(pinyin_cer(s["tts"], hyp), 4),
                                                     logp=round(sc.logp(p, s["tts"]), 2), words=words)
        del sc
    picks = {}
    (AUDIO / "lines").mkdir(exist_ok=True)
    for s in todo:
        rows = report[s["id"]]

        def key(n):
            r = rows[n]
            return (sum(r[m]["cer"] for m in r), -sum(r[m]["logp"] for m in r))

        best = min(rows, key=key)
        picks[s["id"]] = best
        shutil.copy(AUDIO / "takes" / best, AUDIO / "lines" / f"s{s['id']:02d}.mp3")
        print(f"S{s['id']:02d} 台本: {s['tts']}")
        for n in sorted(rows, key=key):
            r = rows[n]
            mark = "★" if n == best else " "
            print(f"  {mark} {n}  cer {r['large-v3-turbo']['cer']:.3f}/{r['medium']['cer']:.3f}"
                  f"  logp {r['large-v3-turbo']['logp']:.1f}/{r['medium']['logp']:.1f}"
                  f"  turbo: {r['large-v3-turbo']['hyp']}  | medium: {r['medium']['hyp']}")
    old_report.update({str(k): v for k, v in report.items()})
    old_picks.update({str(k): v for k, v in picks.items()})
    (WORK / "asr_takes.json").write_text(json.dumps(old_report, ensure_ascii=False, indent=1))
    (WORK / "picks.json").write_text(json.dumps(old_picks, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
