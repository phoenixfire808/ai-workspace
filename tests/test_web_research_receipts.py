from __future__ import annotations

import json
import unittest

from backend.web_research import build_research_context


class WebResearchReceiptTests(unittest.TestCase):
    def test_context_packet_drops_non_public_and_non_http_sources(self) -> None:
        packet = json.loads(
            build_research_context.invoke({
                "sources": [
                    {"source_id": "private", "url": "http://127.0.0.1:8080/private", "title": "private"},
                    {"source_id": "script", "url": "javascript:alert(1)", "title": "script"},
                ],
                "context_text": "bounded context",
            })
        )
        self.assertEqual(packet["status"], "completed")
        self.assertEqual(packet["selected_count"], 0)
        self.assertEqual(packet["sources"], [])
        self.assertNotIn("127.0.0.1", packet["context"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
