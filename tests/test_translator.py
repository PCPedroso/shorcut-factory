import os
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from core.translator import (
    format_translation_prompt,
    translate_transcript_segments,
    save_translated_transcript,
    restore_original_transcript,
    has_original_backup,
    LANGUAGE_NAMES,
)


class TestTranslator(unittest.TestCase):

    def setUp(self):
        self.sample_segments = [
            {"start": 0.0, "end": 4.5, "text": "Hello world, welcome to our presentation today."},
            {"start": 4.5, "end": 9.2, "text": "This technology is going to change everything we know about AI.", "words": [{"word": "This", "start": 4.5, "end": 5.0}]},
            {"start": 9.2, "end": 14.0, "text": "Let us see the live demonstration now."}
        ]

    def test_format_translation_prompt(self):
        items = [{"id": 0, "text": "Hello world"}]
        prompt = format_translation_prompt(items, "Português (Brasil)", "Inglês (English)")
        self.assertIn("Português (Brasil)", prompt)
        self.assertIn("Hello world", prompt)
        self.assertIn("STRICT RULES", prompt)

    @patch("core.translator._call_ollama_json")
    def test_translate_transcript_segments_preserves_timing(self, mock_ollama):
        mock_ollama.return_value = [
            {"id": 0, "text": "Olá mundo, bem-vindos à nossa apresentação de hoje."},
            {"id": 1, "text": "Esta tecnologia vai mudar tudo o que sabemos sobre IA."},
            {"id": 2, "text": "Vejamos a demonstração ao vivo agora."}
        ]

        res = translate_transcript_segments(
            segments=self.sample_segments,
            target_lang="pt-BR",
            model="llama3",
            batch_size=10
        )

        self.assertIsNone(res["error"])
        self.assertEqual(len(res["segments"]), 3)
        self.assertIn("Olá mundo", res["segments"][0]["text"])
        self.assertEqual(res["segments"][0]["start"], 0.0)
        self.assertEqual(res["segments"][0]["end"], 4.5)
        self.assertEqual(res["segments"][1]["start"], 4.5)
        self.assertEqual(res["segments"][1]["end"], 9.2)
        # Verifica que palavras antigas em inglês foram removidas para interpolação limpa
        self.assertNotIn("words", res["segments"][1])
        self.assertIn("Olá mundo", res["full_text"])

    def test_save_and_restore_original_transcript(self):
        temp_dir = tempfile.mkdtemp()
        try:
            # Configura estrutura temporária simulando data/<video_id>
            vid = "test_vid_123"
            orig_data_dir = os.path.join("data", vid)
            os.makedirs(orig_data_dir, exist_ok=True)

            active_path = os.path.join(orig_data_dir, "transcript.json")
            orig_content = {
                "text": "Hello world original",
                "segments": [{"start": 0.0, "end": 2.0, "text": "Hello world original"}],
                "language": "en"
            }
            with open(active_path, "w", encoding="utf-8") as f:
                json.dump(orig_content, f)

            self.assertFalse(has_original_backup(vid))

            translated_data = {
                "full_text": "Olá mundo traduzido",
                "segments": [{"start": 0.0, "end": 2.0, "text": "Olá mundo traduzido"}]
            }

            saved = save_translated_transcript(vid, translated_data, "pt-BR")
            self.assertTrue(saved)
            self.assertTrue(has_original_backup(vid))

            # Verifica que o transcript.json atual é o traduzido
            with open(active_path, "r", encoding="utf-8") as f:
                current_data = json.load(f)
            self.assertEqual(current_data["text"], "Olá mundo traduzido")
            self.assertTrue(current_data["is_translated"])

            # Restaura original
            restored = restore_original_transcript(vid)
            self.assertIsNotNone(restored)
            self.assertEqual(restored["text"], "Hello world original")

            with open(active_path, "r", encoding="utf-8") as f:
                reloaded = json.load(f)
            self.assertEqual(reloaded["text"], "Hello world original")

        finally:
            if os.path.exists(os.path.join("data", "test_vid_123")):
                shutil.rmtree(os.path.join("data", "test_vid_123"), ignore_errors=True)
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("core.translator._call_ollama_json")
    def test_translate_cut_subtitles(self, mock_ollama):
        mock_ollama.return_value = [
            {"id": 0, "text": "Eu gostaria de anunciar que temos uma nova proposta."}
        ]

        vid = "test_vid_cut_99"
        orig_data_dir = os.path.join("data", vid)
        os.makedirs(orig_data_dir, exist_ok=True)
        active_path = os.path.join(orig_data_dir, "transcript.json")

        initial_content = {
            "text": "Introduction part. I would like to announce that we have a new proposal. Closing part.",
            "segments": [
                {"start": 0.0, "end": 10.0, "text": "Introduction part."},
                {"start": 10.0, "end": 20.0, "text": "I would like to announce that we have a new proposal."},
                {"start": 20.0, "end": 30.0, "text": "Closing part."}
            ]
        }
        with open(active_path, "w", encoding="utf-8") as f:
            json.dump(initial_content, f)

        try:
            from core.translator import translate_cut_subtitles
            res = translate_cut_subtitles(
                video_id=vid,
                start_time_str="00:10",
                end_time_str="00:20",
                target_lang="pt-BR"
            )

            self.assertIsNone(res["error"])
            self.assertEqual(res["count"], 1)
            self.assertIn("gostaria de anunciar", res["translated_snippet"])

            with open(active_path, "r", encoding="utf-8") as f:
                saved = json.load(f)

            # Verifica que o segmento 0 e 2 continuam intactos e apenas o segmento 1 foi traduzido
            self.assertEqual(saved["segments"][0]["text"], "Introduction part.")
            self.assertIn("gostaria de anunciar", saved["segments"][1]["text"])
            self.assertEqual(saved["segments"][2]["text"], "Closing part.")

        finally:
            if os.path.exists(orig_data_dir):
                shutil.rmtree(orig_data_dir, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
