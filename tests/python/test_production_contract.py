import json
import shutil
import sys
import unittest
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "lib"))

from src.contracts import production_contract  # noqa: E402
import provider_menu  # noqa: E402


class ProductionContractTest(unittest.TestCase):
    def setUp(self):
        self.workspace = ROOT / "output" / f"test_production_contract_{uuid4().hex}"
        (self.workspace / "work").mkdir(parents=True)
        (self.workspace / "qa").mkdir()

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_delivery_promise_prefers_tts_led_for_narrated_general_video(self):
        promise = production_contract.build_delivery_promise(
            user_requirements="做一个30秒有旁白的知识讲解短视频",
            route="general_video",
            needs_audio=True,
        )

        self.assertEqual(promise["schema"], "capsule_cinema.delivery_promise.v1")
        self.assertEqual(promise["promise_type"], "tts_led_explainer")
        self.assertIn("TTS duration", " ".join(promise["qa_requirements"]))

    def test_delivery_promise_prefers_explicit_capsule_over_reference_words(self):
        promise = production_contract.build_delivery_promise(
            user_requirements="请按胶囊做，里面有参考图和 reference assets，不是复刻参考视频",
            route="capsule",
            capsule_name="life_sim",
            capsule_category="douyin_story_voiceover",
            has_reference_material=True,
            needs_audio=True,
        )

        self.assertEqual(promise["promise_type"], "capsule_preset")

    def test_specialized_categories_are_not_misclassified_as_generic_capsules(self):
        for category in [
            "action-animation",
            "action_animation",
            "action_transfer",
            "code-rendered-graphics",
            "code_rendered_graphics",
            "digital-human",
            "digital_human",
            "lip-sync",
            "lip_sync",
            "music-mv",
            "music_mv",
            "super-resolution",
            "super_resolution",
        ]:
            with self.subTest(category=category):
                promise = production_contract.build_delivery_promise(
                    user_requirements="用专用工具路线生成",
                    route="capsule",
                    capsule_name=f"{category}_capsule",
                    capsule_category=category,
                )

                self.assertEqual(promise["promise_type"], "specialized_route")

    def test_writes_proposal_and_appends_decision_log(self):
        promise = production_contract.build_delivery_promise(
            user_requirements="用 healing_asmr 胶囊做一个羊毛毡甜点视频",
            route="capsule",
            capsule_name="healing_asmr",
            capsule_category="asmr",
            needs_audio=False,
        )
        proposal = production_contract.build_production_proposal(
            user_requirements="羊毛毡甜点",
            delivery_promise=promise,
            route="capsule",
            aspect_ratio="9:16",
            target_duration=30,
            tool_route={"video_engine": "seedance-fast", "image_engine": "seedream5"},
            risks=["capsule assets must stay local"],
            release_bar=["release checkpoint must pass"],
        )

        proposal_path = production_contract.write_production_proposal(self.workspace, proposal)
        decision_path = production_contract.append_decision(
            self.workspace,
            category="delivery_promise",
            selected=promise["promise_type"],
            options_considered=["capsule_preset", "tts_led_explainer"],
            reason="A capsule was explicitly selected.",
            user_visible=True,
            user_approved=True,
            confidence=0.8,
            qa_impact="Capsule quality rules are release gates.",
        )

        proposal_payload = json.loads(proposal_path.read_text(encoding="utf-8"))
        decision_payload = json.loads(decision_path.read_text(encoding="utf-8"))

        self.assertEqual(proposal_payload["schema"], "capsule_cinema.production_proposal.v1")
        self.assertEqual(proposal_payload["delivery_promise"]["promise_type"], "capsule_preset")
        self.assertEqual(decision_payload["schema"], "capsule_cinema.decision_log.v1")
        self.assertEqual(decision_payload["decisions"][0]["category"], "delivery_promise")
        self.assertEqual(decision_payload["decisions"][0]["selected"], "capsule_preset")

    def test_provider_menu_summarizes_registered_tools_by_capability(self):
        menu = provider_menu.build_provider_menu()

        self.assertEqual(menu["schema"], "capsule_cinema.provider_menu.v1")
        self.assertTrue(menu["registry_path"].endswith("tool_capabilities.yaml"))
        categories = {item["category"]: item for item in menu["capabilities"]}
        self.assertIn("video_generation", categories)
        video_tools = {
            tool["name"]: tool
            for tool in categories["video_generation"]["tools"]
        }
        self.assertIn("SeedanceFastVideoGeneratorTool", video_tools)
        self.assertIn("provides", video_tools["SeedanceFastVideoGeneratorTool"])
        self.assertIn("requires_env", video_tools["SeedanceFastVideoGeneratorTool"])
        self.assertIn("image_generation", categories)


if __name__ == "__main__":
    unittest.main()
