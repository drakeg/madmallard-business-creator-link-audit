"""Keep automated dependency PRs within the tested Django LTS line."""
import json
import unittest
from pathlib import Path
from packaging.specifiers import SpecifierSet
from packaging.version import Version

ROOT=Path(__file__).resolve().parents[1]

class RenovateLTSGuardTests(unittest.TestCase):
    def test_django_5_2_patch_allowed_but_django_6_major_blocked(self):
        data=json.loads((ROOT/"renovate.json").read_text())
        matching=[
            rule for rule in data.get("packageRules",[])
            if "django" in rule.get("matchPackageNames",[])
            and "pypi" in rule.get("matchDatasources",[])
        ]
        self.assertTrue(matching,"Django Renovate LTS policy is missing")
        allowed=SpecifierSet(matching[-1]["allowedVersions"])
        self.assertIn(Version("5.2.19"),allowed)
        self.assertIn(Version("5.2.20"),allowed)
        self.assertNotIn(Version("6.0.0"),allowed)
        self.assertNotIn(Version("6.1.0"),allowed)

if __name__=="__main__":
    unittest.main()
