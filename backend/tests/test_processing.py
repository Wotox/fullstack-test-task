from pathlib import Path
import tempfile
import unittest

from src.processing import build_alert, extract_metadata, scan_file


class ProcessingTests(unittest.TestCase):
    def test_scan_marks_suspicious_extension(self) -> None:
        result = scan_file("run.exe", "application/octet-stream", 42)

        self.assertEqual(result.status, "suspicious")
        self.assertTrue(result.requires_attention)
        self.assertIn("suspicious extension .exe", result.details)

    def test_scan_marks_clean_file(self) -> None:
        result = scan_file("notes.txt", "text/plain", 42)

        self.assertEqual(result.status, "clean")
        self.assertFalse(result.requires_attention)
        self.assertEqual(result.details, "no threats found")

    def test_extracts_text_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "notes.txt"
            path.write_text("one\ntwo\n", encoding="utf-8")

            metadata = extract_metadata("notes.txt", "text/plain", 8, path)

        self.assertEqual(metadata["extension"], ".txt")
        self.assertEqual(metadata["line_count"], 2)
        self.assertEqual(metadata["char_count"], 8)

    def test_pdf_page_counter_does_not_count_pages_node(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "doc.pdf"
            path.write_bytes(b"/Type /Pages /Type /Page /Type /Page")

            metadata = extract_metadata("doc.pdf", "application/pdf", 36, path)

        self.assertEqual(metadata["approx_page_count"], 2)

    def test_builds_warning_alert(self) -> None:
        alert = build_alert("processed", True, "suspicious extension .js")

        self.assertEqual(alert.level, "warning")
        self.assertEqual(alert.message, "File requires attention: suspicious extension .js")


if __name__ == "__main__":
    unittest.main()
