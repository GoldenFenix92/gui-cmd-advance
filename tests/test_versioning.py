import os
import unittest

from functions import versioning
from scripts import build_exe


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestVersioningSystem(unittest.TestCase):
    def test_canonical_version_file_exists_and_is_valid_semver(self):
        version_path = os.path.join(PROJECT_ROOT, "VERSION")
        self.assertTrue(os.path.isfile(version_path), "Falta el archivo canónico VERSION en la raíz.")
        ver = versioning.read_canonical_version(version_path)
        self.assertTrue(versioning.is_valid_canonical_semver(ver), f"VERSION inválida: {ver!r}")
        self.assertEqual(versioning.get_app_version(), ver)

    def test_canonical_semver_validation(self):
        valid = ["2.0.0", "2.0.0-beta", "2.0.0-beta.1", "2.1.3-rc.2", "0.9.1-alpha.3"]
        for v in valid:
            self.assertTrue(versioning.is_valid_canonical_semver(v), f"Debió ser válida: {v}")

        invalid = ["", "v2.0.0", "2.0", "2.0.0 Beta", "1.0.126.0", "2.0.0-beta.0", "02.0.0", "abc"]
        for v in invalid:
            self.assertFalse(versioning.is_valid_canonical_semver(v), f"Debió ser inválida: {v}")

    def test_is_newer_version_prevents_beta_loops_and_downgrades(self):
        # Misma versión en distintos formatos -> nunca debe disparar actualización
        self.assertFalse(versioning.is_newer_version("v2.0.0-beta", "2.0.0-beta"))
        self.assertFalse(versioning.is_newer_version("2.0.0-beta", "2.0.0 Beta"))
        self.assertFalse(versioning.is_newer_version("v1.0.126-beta", "1.0.126 Beta"))
        self.assertFalse(versioning.is_newer_version("v2.0.0", "2.0.0"))

        # Downgrades -> siempre False
        self.assertFalse(versioning.is_newer_version("v1.0.126-beta", "2.0.0-beta"))
        self.assertFalse(versioning.is_newer_version("v1.9.9", "2.0.0-beta"))
        self.assertFalse(versioning.is_newer_version("v2.0.0-beta", "2.0.0"))
        self.assertFalse(versioning.is_newer_version("v2.0.0-beta.1", "2.0.0-beta.2"))
        self.assertFalse(versioning.is_newer_version("v2.0.0-alpha.5", "2.0.0-beta"))

        # Upgrades legítimos -> True
        self.assertTrue(versioning.is_newer_version("v2.0.0-beta", "1.0.126 Beta"))
        self.assertTrue(versioning.is_newer_version("v2.0.0-beta.1", "2.0.0-beta"))
        self.assertTrue(versioning.is_newer_version("v2.0.0-beta.2", "2.0.0-beta.1"))
        self.assertTrue(versioning.is_newer_version("v2.0.0-rc.1", "2.0.0-beta.9"))
        self.assertTrue(versioning.is_newer_version("v2.0.0", "2.0.0-beta"))
        self.assertTrue(versioning.is_newer_version("v2.0.0", "2.0.0-rc.2"))
        self.assertTrue(versioning.is_newer_version("v2.1.0", "2.0.9"))
        self.assertTrue(versioning.is_newer_version("v3.0.0-alpha.1", "2.9.9"))

        # Entradas inválidas -> seguro (False)
        self.assertFalse(versioning.is_newer_version("", "2.0.0-beta"))
        self.assertFalse(versioning.is_newer_version("invalid", "2.0.0-beta"))
        self.assertFalse(versioning.is_newer_version("v2.0.0", None))

    def test_windows_version_tuple_and_git_tag(self):
        self.assertEqual(versioning.to_windows_version_tuple("2.0.0-beta", 136), (2, 0, 0, 136))
        self.assertEqual(versioning.to_windows_version_tuple("2.1.4", 200), (2, 1, 4, 200))
        self.assertEqual(versioning.to_windows_version_tuple("2.0.0", 99999), (2, 0, 0, 65535))
        self.assertEqual(versioning.format_git_tag("2.0.0-beta"), "v2.0.0-beta")
        self.assertEqual(versioning.format_git_tag("v2.0.0"), "v2.0.0")

    def test_build_exe_resolves_canonical_version_and_channel(self):
        meta_beta = build_exe.resolve_build_metadata(version_override="2.0.0-beta", commit_count=136)
        self.assertEqual(meta_beta["version"], "2.0.0-beta")
        self.assertEqual(meta_beta["git_tag"], "v2.0.0-beta")
        self.assertTrue(meta_beta["is_prerelease"])
        self.assertEqual(meta_beta["exe_name"], "Gui Cmd Advance Beta")
        self.assertEqual(meta_beta["win_tuple"], (2, 0, 0, 136))
        self.assertEqual(meta_beta["file_version"], "2.0.0.136")

        meta_stable = build_exe.resolve_build_metadata(version_override="2.0.0", commit_count=140)
        self.assertFalse(meta_stable["is_prerelease"])
        self.assertEqual(meta_stable["exe_name"], "Gui Cmd Advance")
        self.assertEqual(meta_stable["file_version"], "2.0.0.140")

        # Resolución por defecto debe coincidir con la versión activa detectada
        meta_default = build_exe.resolve_build_metadata(commit_count=139)
        self.assertEqual(meta_default["version"], versioning.get_app_version())

    def test_classify_commit_impact_and_bump_semver(self):
        self.assertEqual(versioning.classify_commit_impact(["docs: update README", "test: add cases"]), "none")
        self.assertEqual(versioning.classify_commit_impact(["fix(ui): center modal"]), "patch")
        self.assertEqual(versioning.classify_commit_impact(["fix(ui): minor", "feat(drag-drop): native drop"]), "minor")
        self.assertEqual(versioning.classify_commit_impact(["feat(ui)!: new framework"]), "major")
        self.assertEqual(
            versioning.classify_commit_impact(["refactor: core\n\nBREAKING CHANGE: config schema"]),
            "major",
        )

        # Estables
        self.assertEqual(versioning.bump_semver("2.0.0", "none"), "2.0.0")
        self.assertEqual(versioning.bump_semver("2.0.0", "patch"), "2.0.1")
        self.assertEqual(versioning.bump_semver("2.0.0", "minor"), "2.1.0")
        self.assertEqual(versioning.bump_semver("2.0.0", "major"), "3.0.0")

        # Pre-releases: siempre '-beta' limpio sin sufijos .1 / .2
        self.assertEqual(versioning.bump_semver("2.0.0-beta", "minor"), "2.1.0-beta")
        self.assertEqual(versioning.bump_semver("2.1.0-beta", "patch"), "2.1.1-beta")
        self.assertEqual(versioning.bump_semver("2.1.1-beta", "none"), "2.1.1-beta")
        self.assertEqual(versioning.bump_semver("2.1.0-beta", "major"), "3.0.0-beta")

        # Cambio de canal Beta <-> Estable y prompt interactivo de build_exe
        self.assertEqual(versioning.apply_release_channel("2.1.0-beta.2", True), "2.1.0-beta")
        self.assertEqual(versioning.apply_release_channel("2.1.0-beta", False), "2.1.0")

        meta_forced_beta = build_exe.resolve_build_metadata(version_override="2.1.0-beta.1", commit_count=140, is_beta=True)
        self.assertEqual(meta_forced_beta["version"], "2.1.0-beta")
        self.assertEqual(meta_forced_beta["exe_name"], "Gui Cmd Advance Beta")

        meta_forced_stable = build_exe.resolve_build_metadata(version_override="2.1.0-beta", commit_count=140, is_beta=False)
        self.assertEqual(meta_forced_stable["version"], "2.1.0")
        self.assertEqual(meta_forced_stable["exe_name"], "Gui Cmd Advance")

        self.assertTrue(build_exe.prompt_beta_channel(default_is_beta=False, input_fn=lambda _p: "s"))
        self.assertFalse(build_exe.prompt_beta_channel(default_is_beta=True, input_fn=lambda _p: "n"))
        self.assertTrue(build_exe.prompt_beta_channel(default_is_beta=True, input_fn=lambda _p: ""))

    def test_telemetry_uses_semantic_comparator_and_rule_exists(self):
        telemetry_path = os.path.join(PROJECT_ROOT, "functions", "telemetry.py")
        with open(telemetry_path, "r", encoding="utf-8") as f:
            src = f.read()
        self.assertIn("is_newer_version", src)
        self.assertNotIn("latest_tag != current", src)

        rule_path = os.path.join(PROJECT_ROOT, ".agents", "rules", "version-audit.md")
        self.assertTrue(os.path.isfile(rule_path), "Falta la regla exclusiva .agents/rules/version-audit.md")


if __name__ == "__main__":
    unittest.main()
