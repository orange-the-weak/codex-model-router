import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "tests" / "validate_distribution.py"


class DistributionValidatorPortabilityTests(unittest.TestCase):
    def test_every_text_read_declares_utf8(self):
        tree = ast.parse(VALIDATOR.read_text(encoding="utf-8"))
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "read_text"
        ]

        self.assertTrue(calls)
        for call in calls:
            encodings = [
                keyword.value
                for keyword in call.keywords
                if keyword.arg == "encoding"
            ]
            self.assertEqual(len(encodings), 1)
            self.assertIsInstance(encodings[0], ast.Constant)
            self.assertEqual(encodings[0].value, "utf-8")


if __name__ == "__main__":
    unittest.main()
