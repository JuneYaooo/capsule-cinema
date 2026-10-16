"""成片验收：whisper medium + large-v3-turbo 全片转写，对照台本算无调拼音 CER，列出逐句差异。

python3.12 asr_final.py ../final.mp4 | tee ../qa/asr_final.log
两个模型都要看：CER 不为 0 的句子逐条试听；分不清是念错还是转写偏好，就把那个词放进 asr_force.py 的 CASES。
medium 偶尔会输出繁体字，造成假的「差 1 字」，对照转写原文就能看出来。
"""
import sys
from pathlib import Path

import whisper
from pypinyin import lazy_pinyin

WORK = Path(__file__).resolve().parent
sys.path.insert(0, str(WORK))
from asr_pick import edit_distance, normalize  # noqa: E402
from episode import SENTENCES  # noqa: E402

video = Path(sys.argv[1]).resolve()
ref = "".join(s["tts"] for s in SENTENCES)
ref_py = lazy_pinyin(normalize(ref))
for name in ("medium", "large-v3-turbo"):
    m = whisper.load_model(name)
    r = m.transcribe(str(video), language="zh", initial_prompt="以下是普通话的句子。", condition_on_previous_text=False)
    hyp = "".join(seg["text"] for seg in r["segments"])
    hyp_py = lazy_pinyin(normalize(hyp))
    cer = edit_distance(ref_py, hyp_py) / len(ref_py)
    print(f"== {name}  pinyin CER {cer:.3f}  ({len(ref_py)} 字)")
    for seg in r["segments"]:
        print(f"  {seg['start']:6.2f}-{seg['end']:6.2f} {seg['text']}")
    # 逐句：在转写里找最像的一段（滑窗），只报有差异的
    for s in SENTENCES:
        rp = lazy_pinyin(normalize(s["tts"]))
        best = min(((edit_distance(rp, hyp_py[i:i + len(rp)]), i) for i in range(max(1, len(hyp_py) - len(rp) + 1))))
        if best[0]:
            i = best[1]
            hyp_chars = normalize(hyp)
            print(f"  S{s['id']:02d} 差 {best[0]} 字：台本「{normalize(s['tts'])}」 转写「{hyp_chars[i:i + len(rp)]}」")
