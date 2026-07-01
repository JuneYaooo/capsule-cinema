import json
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CAPSULE_PATH = ROOT / "capsules" / "tiktok_15s_product_ad.capsule.zip"


class TikTok15sProductAdCapsuleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with zipfile.ZipFile(CAPSULE_PATH) as package:
            cls.manifest = json.loads(package.read("manifest.json").decode("utf-8"))
        cls.capsule = cls.manifest["capsule"]

    def test_capsule_reuses_ecommerce_runtime_route(self):
        capsule = self.capsule
        config = capsule["config"]
        method_text = json.dumps(capsule["method"], ensure_ascii=False)

        self.assertEqual(capsule["name"], "tiktok_15s_product_ad")
        self.assertEqual(capsule["execution_mode"], "preset")
        self.assertEqual(capsule["category"], "ecommerce_product_showcase")
        self.assertEqual(config["roles"]["image"]["validated_with"], "GptImage2Tool")
        self.assertEqual(config["roles"]["video"]["validated_with"], "Seedance20VideoGeneratorTool")
        self.assertIn("object_reference", method_text)
        self.assertIn("gpt-image-2", method_text)
        self.assertIn("Seedance 2.0", method_text)

    def test_exact_15s_four_scene_contract(self):
        config = self.capsule["config"]
        output_contract = config["output_contract"]
        method = self.capsule["method"]

        self.assertEqual(config["target_duration_seconds"], 15)
        self.assertEqual(config["target_duration_range"], [15, 15])
        self.assertEqual(config["generated_scene_count_range"], [4, 4])
        self.assertEqual(config["scene_duration_pattern_seconds"], [3, 4, 5, 3])
        self.assertEqual(output_contract["duration_seconds_range"], [15, 15])
        self.assertEqual(output_contract["scene_count_range"], [4, 4])
        self.assertEqual(output_contract["clip_audio"], "silent")
        self.assertEqual(output_contract["voice"], "unified_tts")
        self.assertEqual(output_contract["subtitle"], "overlay")
        self.assertEqual(output_contract["bgm"], "external")
        self.assertEqual(output_contract["on_frame_text"], "none")
        self.assertEqual(
            [scene["duration_seconds"] for scene in method["script_output_contract"]["scene_pattern"]],
            [3, 4, 5, 3],
        )

    def test_ports_core_creative_director_rules_from_skill(self):
        method = self.capsule["method"]
        method_text = json.dumps(method, ensure_ascii=False)

        self.assertEqual(len(method["creative_dimensions"]), 6)
        self.assertEqual(len(method["narrative_archetypes"]), 5)
        self.assertIn("single differentiated selling point", method["capsule_intent"])
        self.assertIn("used_creative_history", method_text)
        self.assertIn("black-and-white to color explosion", method_text)
        self.assertIn("kitchen-scale weighing proof", method_text)
        self.assertIn("2.5 English words per second", method_text)
        self.assertIn("best-friend", method_text)
        self.assertIn("defocus-to-refocus", method_text)
        self.assertIn("zoom-in-to-zoom-out", method_text)

    def test_product_id_lookup_is_safe_optional_enrichment(self):
        method = self.capsule["method"]
        input_schema = self.capsule["input_schema"]
        method_text = json.dumps(method, ensure_ascii=False)

        self.assertIn("product_id", input_schema)
        self.assertIn("product_url", input_schema)
        self.assertIn("product_title_en", input_schema)
        self.assertIn("used_creative_history", input_schema)
        self.assertIn("If enrichment is unavailable", method_text)
        self.assertIn("do not hallucinate product facts", method_text)
        self.assertIn("manual product title", method_text)

    def test_casting_policy_is_diverse_without_hardcoded_exclusion(self):
        method_text = json.dumps(self.capsule["method"], ensure_ascii=False).lower()

        self.assertIn("do not exclude any ethnicity", method_text)
        self.assertNotIn("非亚洲人", method_text)
        self.assertNotIn("non-asian", method_text)

    def test_quality_rules_cover_ad_specific_gates(self):
        rule_ids = {rule.get("id") for rule in self.capsule["quality_rules"]}

        self.assertIn("exact_15s_four_scene_contract", rule_ids)
        self.assertIn("single_differentiated_selling_point", rule_ids)
        self.assertIn("creative_dimension_and_archetype_selected", rule_ids)
        self.assertIn("creative_deduplication", rule_ids)
        self.assertIn("product_reference_anchor", rule_ids)
        self.assertIn("scene_level_object_reference_required", rule_ids)
        self.assertIn("visual_gag_not_factual_claim", rule_ids)
        self.assertIn("no_category_default_claims", rule_ids)
        self.assertIn("voiceover_duration_fit", rule_ids)
        self.assertIn("no_invented_commercial_claims", rule_ids)

    def test_product_scene_references_are_explicit_and_mixed(self):
        method = self.capsule["method"]
        contract = method["script_output_contract"]["scene_reference_field_contract"]
        method_text = json.dumps(method, ensure_ascii=False)

        self.assertIn("when_product_image_present", contract)
        self.assertIn("reference_type=mixed", method_text)
        self.assertIn("character-only", method_text)
        self.assertIn("object_reference", method_text)
        self.assertIn("visual metaphors", method_text)
        self.assertIn("will not pop a balloon", method_text)

    def test_category_default_claims_are_forbidden(self):
        method = self.capsule["method"]
        method_text = json.dumps(method, ensure_ascii=False).lower()
        forbidden = method["product_fact_contract"]["forbidden_inventions"]

        self.assertIn("body-relief claim", forbidden)
        self.assertIn("environmental-isolation claim", forbidden)
        self.assertIn("pairing-speed claim", forbidden)
        self.assertIn("category-default claims", method_text)
        self.assertIn("daily workflow friction", method_text)
        self.assertIn("body-relief", method_text)
        self.assertIn("battery", method_text)


if __name__ == "__main__":
    unittest.main()
