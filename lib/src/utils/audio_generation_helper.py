from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from custom_tools.audio_generation import UniversalTTSTool


class AudioGenerationHelper:
    def __init__(self, max_workers=3):
        self.max_workers = max_workers

    def generate_audios_concurrent(self, storyboard, voice_map, audios_dir, max_retries=2):
        del max_retries
        Path(audios_dir).mkdir(parents=True, exist_ok=True)
        tool = UniversalTTSTool()

        def run_scene(index, scene):
            voice = voice_map.get(scene.get("character_tag")) or voice_map.get("main") or {}
            text = scene.get("narration") or scene.get("subtitle") or scene.get("subtitle_text") or ""
            if not text:
                return index, None
            output_path = str(Path(audios_dir) / f"scene_{index:02d}.mp3")
            return index, tool._run(
                text=text,
                voice_type=voice.get("voice_type") or voice.get("voice") or "zh_male_jieshuoxiaoming_moon_bigtts",
                speed=voice.get("speed_ratio") or voice.get("speed") or 1.1,
                output_path=output_path,
            )

        outputs = [None] * len(storyboard)
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(run_scene, i, scene) for i, scene in enumerate(storyboard)]
            for future in as_completed(futures):
                index, result = future.result()
                if isinstance(result, dict):
                    outputs[index] = result.get("audio_path") or result.get("output_path")
                else:
                    outputs[index] = result

        return {
            "outputs": outputs,
            "summary": {
                "total": len(storyboard),
                "successful": sum(bool(item) for item in outputs),
            },
        }
