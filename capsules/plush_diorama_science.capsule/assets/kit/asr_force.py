"""强制解码打分：判断「念错」还是「转写偏好」。

python3.12 asr_force.py [large-v3-turbo|medium]   → asr_force_<模型>.json

对每个可疑点，把正确写法和转写写法分别接在 sot 序列后面，累加 token log prob，
算 Δ = 正确 − 错误（nats）。配本句音频算一次、配 3 秒静音算一次：
静音那次是语言偏好；配上音频后 Δ 明显为负，才说明音频里真是那样念的。
"""
import json
import sys
from pathlib import Path

import numpy as np
import torch
import whisper

WORK = Path(__file__).resolve().parent
AUDIO = WORK.parent / "audio" / "lines"  # 挑好的 take：sNN.mp3

# (句号, 正确写法, 可疑写法) —— 两条文字只在可疑的那个词上不同，其余一字不差。
# 可疑写法照抄 asr_final / asr_pick 转写出来的样子，例如 (3, "<正确的半句>", "<转写成的半句>")。
CASES = [
]


def main(model_name):
    if not CASES:
        sys.exit("CASES 是空的：把可疑的 (句号, 正确写法, 可疑写法) 填进去再跑")
    m = whisper.load_model(model_name)
    tok = whisper.tokenizer.get_tokenizer(m.is_multilingual, num_languages=m.num_languages,
                                          language="zh", task="transcribe")
    sot = list(tok.sot_sequence_including_notimestamps)

    def feats_of(audio):
        audio = whisper.pad_or_trim(audio)
        mel = whisper.log_mel_spectrogram(audio, n_mels=m.dims.n_mels).to(m.device)
        with torch.no_grad():
            return m.embed_audio(mel[None])

    def score(feats, text):
        toks = sot + tok.encode(text) + [tok.eot]
        x = torch.tensor([toks], device=m.device)
        with torch.no_grad():
            logp = torch.log_softmax(m.logits(x[:, :-1], feats).float(), -1)
        lp = logp.gather(-1, x[:, 1:, None]).squeeze(-1)[0]
        return float(lp[len(sot) - 1:].sum())

    silence = feats_of(np.zeros(16000 * 3, np.float32))
    rows = []
    for lid, good, bad in CASES:
        feats = feats_of(whisper.load_audio(str(AUDIO / f"s{lid:02d}.mp3")))
        d_audio = score(feats, good) - score(feats, bad)
        d_text = score(silence, good) - score(silence, bad)
        verdict = "念错" if d_audio < -1.0 and d_audio < d_text else ("对" if d_audio > 1.0 else "待定")
        rows.append(dict(line=lid, good=good, bad=bad, d_audio=round(d_audio, 2), d_text=round(d_text, 2),
                         verdict=verdict))
        print(f"L{lid:02d} {good} vs {bad}: 配音频 {d_audio:+.2f}  只给文字 {d_text:+.2f}  → {verdict}", flush=True)
    (WORK / f"asr_force_{model_name}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "large-v3-turbo")
