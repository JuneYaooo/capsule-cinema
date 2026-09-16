#!/usr/bin/env python3.12
"""Cross-surface consistency lint for capsule packages.

A capsule rule must have exactly one home: craft reasoning in recipes/,
enforceable thresholds and enums in contracts/ and quality/. When surfaces
drift apart across updates, contradictions reach the planning agent. This
lint catches the mechanical part of that drift:

- errors: broken read_order/index links, recipes missing from read_order,
  capability vocabulary violations
- warnings: schema enums never grounded in recipe prose, numeric thresholds
  present in QA rules but in no recipe, over-length summaries

Usage:
    PYTHONPATH=lib python3.12 scripts/capsule_consistency_lint.py [capsule_dir ...]

With no arguments, lints every capsules/*.capsule directory. Exit code is 1
only on errors; warnings require human review but do not fail.
"""

from __future__ import annotations

import glob
import os
import re
import sys

try:
    import yaml
except ImportError:  # pragma: no cover
    print("PyYAML is required: python3.12 -m pip install pyyaml", file=sys.stderr)
    sys.exit(2)

SUMMARY_MAX_CHARS = 160
CARD_DESCRIPTION_MAX_CHARS = 240

_CHINESE_DIGITS = {
    "零": "0", "一": "1", "二": "2", "两": "2", "三": "3", "四": "4",
    "五": "5", "六": "6", "七": "7", "八": "8", "九": "9",
}


def _normalize_digits(text: str) -> str:
    for zh, digit in _CHINESE_DIGITS.items():
        text = text.replace(zh, digit)
    return text


def _extract_ints(text: str) -> set[int]:
    return {int(n) for n in re.findall(r"\d+", text)}


def _load_yaml(path: str):
    rel = os.path.relpath(path, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        raise YamlBrokenError(f"{rel} is not valid YAML: {exc}") from exc


class YamlBrokenError(Exception):
    pass


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def _frontmatter_value(md_text: str, key: str) -> str | None:
    match = re.search(r"^---\s*\n(.*?)\n---", md_text, re.DOTALL)
    if not match:
        return None
    line = re.search(rf"^{key}:\s*(.+)$", match.group(1), re.MULTILINE)
    return line.group(1).strip() if line else None


class CapsuleLint:
    def __init__(self, capsule_dir: str) -> None:
        self.capsule_dir = capsule_dir
        self.name = os.path.basename(capsule_dir)
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def _rel_exists(self, rel: str) -> bool:
        return os.path.isfile(os.path.join(self.capsule_dir, rel))

    def lint(self) -> None:
        capsule_yaml_path = os.path.join(self.capsule_dir, "capsule.yaml")
        if not os.path.isfile(capsule_yaml_path):
            self.errors.append("capsule.yaml missing")
            return
        try:
            capsule = _load_yaml(capsule_yaml_path) or {}
            if not isinstance(capsule, dict):
                raise YamlBrokenError("capsule.yaml does not parse to a mapping")
            self._lint_read_order(capsule)
            self._lint_index_links()
            self._lint_capabilities(capsule)
            self._lint_enum_grounding()
            self._lint_numeric_grounding()
            self._lint_description_length(capsule)
        except YamlBrokenError as exc:
            self.errors.append(str(exc))

    # --- structure -------------------------------------------------------

    def _lint_read_order(self, capsule: dict) -> None:
        read_order = capsule.get("read_order") or {}
        staged: list[str] = []
        for stage, files in read_order.items():
            if not isinstance(files, list):
                self.errors.append(f"read_order.{stage} is not a list")
                continue
            staged.extend(files)
        for rel in staged:
            if not self._rel_exists(rel):
                self.errors.append(f"read_order file missing: {rel}")
        recipes = sorted(
            os.path.relpath(path, self.capsule_dir)
            for path in glob.glob(os.path.join(self.capsule_dir, "recipes", "*.md"))
        )
        for rel in recipes:
            if rel not in staged:
                self.errors.append(f"recipe not listed in read_order: {rel}")

    def _lint_index_links(self) -> None:
        index_path = os.path.join(self.capsule_dir, "index.md")
        if not os.path.isfile(index_path):
            self.errors.append("index.md missing")
            return
        for target in re.findall(r"\]\(([^)#]+)\)", _read_text(index_path)):
            target = target.strip()
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            if not self._rel_exists(target):
                self.errors.append(f"index.md link broken: {target}")

    # --- capability vocabulary -------------------------------------------

    def _lint_capabilities(self, capsule: dict) -> None:
        capabilities = set(capsule.get("capabilities") or [])
        production = set(capsule.get("production_capabilities") or [])
        if production and not production <= capabilities:
            missing = sorted(production - capabilities)
            self.errors.append(
                "capsule.yaml.production_capabilities not a subset of "
                f"capabilities: {missing}"
            )
        contract_path = os.path.join(self.capsule_dir, "contracts", "production_contract.yaml")
        if os.path.isfile(contract_path):
            contract = _load_yaml(contract_path) or {}
            contract_caps = set(contract.get("production_capabilities") or [])
            if contract_caps and not contract_caps <= (capabilities | production):
                missing = sorted(contract_caps - (capabilities | production))
                self.errors.append(
                    "contracts/production_contract.yaml production_capabilities "
                    f"unknown to capsule.yaml: {missing}"
                )

    # --- grounding -------------------------------------------------------

    def _recipe_text(self) -> str:
        parts = []
        for path in glob.glob(os.path.join(self.capsule_dir, "recipes", "*.md")):
            parts.append(_read_text(path))
        return _normalize_digits("\n".join(parts))

    def _lint_enum_grounding(self) -> None:
        schema_path = os.path.join(self.capsule_dir, "contracts", "input_schema.yaml")
        if not os.path.isfile(schema_path):
            return
        schema = _load_yaml(schema_path) or {}
        fields = (schema.get("fields") or {}).get("episode_content", {})
        properties = fields.get("properties", {}) if isinstance(fields, dict) else {}
        recipe_text = self._recipe_text()
        for field_name, spec in properties.items():
            if not isinstance(spec, dict):
                continue
            for member in spec.get("enum") or []:
                if str(member) not in recipe_text:
                    self.warnings.append(
                        f"input_schema enum value not grounded in recipes: "
                        f"{field_name}={member}"
                    )

    def _lint_numeric_grounding(self) -> None:
        rules_path = os.path.join(self.capsule_dir, "quality", "rules.yaml")
        if not os.path.isfile(rules_path):
            return
        rules = (_load_yaml(rules_path) or {}).get("rules") or []
        recipe_text = self._recipe_text()
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            for number in _extract_ints(str(rule.get("rule", ""))):
                if number >= 1000:  # years, resolutions, ids
                    continue
                if not re.search(rf"(?<!\d){number}(?!\d)", recipe_text):
                    self.warnings.append(
                        f"QA rule '{rule.get('id')}' uses {number} but no recipe "
                        "states it; check for threshold drift"
                    )

    def _lint_description_length(self, capsule: dict) -> None:
        summary = str(capsule.get("summary") or "")
        if len(summary) > SUMMARY_MAX_CHARS:
            self.warnings.append(
                f"capsule.yaml.summary is {len(summary)} chars (>{SUMMARY_MAX_CHARS}); "
                "rewrite in place instead of appending version clauses"
            )
        card_path = os.path.join(self.capsule_dir, "CARD.md")
        if os.path.isfile(card_path):
            description = _frontmatter_value(_read_text(card_path), "description") or ""
            if len(description) > CARD_DESCRIPTION_MAX_CHARS:
                self.warnings.append(
                    f"CARD.md description is {len(description)} chars "
                    f"(>{CARD_DESCRIPTION_MAX_CHARS}); rewrite in place"
                )

    # --- report ----------------------------------------------------------

    def report(self) -> int:
        status = "FAIL" if self.errors else ("WARN" if self.warnings else "PASS")
        print(f"[{status}] {self.name}")
        for message in self.errors:
            print(f"  ERROR {message}")
        for message in self.warnings:
            print(f"  warn  {message}")
        return 1 if self.errors else 0


def main(argv: list[str]) -> int:
    if argv:
        targets = argv
    else:
        root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "capsules")
        targets = sorted(glob.glob(os.path.join(root, "*.capsule")))
    if not targets:
        print("no capsule directories found", file=sys.stderr)
        return 2
    failed = 0
    for target in targets:
        lint = CapsuleLint(target.rstrip("/"))
        lint.lint()
        failed |= lint.report()
    return failed


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
