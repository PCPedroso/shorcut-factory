import unittest
from core.analyzer import (
    parse_time_str_to_seconds,
    format_seconds_to_time,
    format_duration_human,
    _clean_ai_title
)


class TestAnalyzerUtils(unittest.TestCase):

    def test_parse_time_str_to_seconds(self):
        self.assertEqual(parse_time_str_to_seconds("00:01:30"), 90.0)
        self.assertEqual(parse_time_str_to_seconds("01:00:00"), 3600.0)
        self.assertEqual(parse_time_str_to_seconds("02:15"), 135.0)
        self.assertEqual(parse_time_str_to_seconds("45"), 45.0)

    def test_format_seconds_to_time(self):
        self.assertEqual(format_seconds_to_time(90), "00:01:30")
        self.assertEqual(format_seconds_to_time(3665), "01:01:05")
        self.assertEqual(format_seconds_to_time(0), "00:00:00")

    def test_format_duration_human(self):
        self.assertEqual(format_duration_human(90), "1m 30s")
        self.assertEqual(format_duration_human(45), "45s")
        self.assertEqual(format_duration_human(3600), "60m 00s")

    def test_clean_ai_title(self):
        raw1 = '1. "Título: O Brasil vai entrar em recessão?"'
        clean1 = _clean_ai_title(raw1)
        self.assertNotIn("Título:", clean1)
        self.assertNotIn('"', clean1)
        self.assertFalse(clean1.startswith("1."))

        raw2 = "Aqui estão os cortes: Renan Santos desafia o sistema"
        clean2 = _clean_ai_title(raw2)
        self.assertNotIn("Aqui estão", clean2)

    def test_multi_cut_mining_on_long_speech(self):
        from core.analyzer import build_golden_rule_micro_cuts
        
        # Simula uma pauta longa de 240s (4 minutos) com múltiplos pontos de transição
        pautas = [{
            "id": 1,
            "title": "Debate sobre Economia e Segurança",
            "start": "00:01:00",
            "end": "00:05:00",
            "start_s": 60.0,
            "end_s": 300.0,
            "duration_s": 240.0,
            "duration_label": "4m 00s",
            "text_snippet": "Pergunta e resposta longa sobre o futuro do país."
        }]

        segments = [
            {"start": 60.0, "end": 75.0, "text": ">> Qual é a sua proposta para a segurança?"},
            {"start": 76.0, "end": 115.0, "text": ">> Muito obrigado pela pergunta. O primeiro ponto central é a retomada territorial."},
            {"start": 116.0, "end": 155.0, "text": "Por exemplo, no caso da fronteira nós temos que dobrar o policiamento."},
            {"start": 156.0, "end": 195.0, "text": ">> Posso te falar uma coisa? Essa medida já foi tentada antes."},
            {"start": 196.0, "end": 240.0, "text": ">> Grande pergunta. A diferença é que agora temos tecnologia de ponta e drones."},
            {"start": 241.0, "end": 298.0, "text": "Em resumo, sem segurança jurídica não há crescimento econômico para o cidadão."}
        ]

        cuts = build_golden_rule_micro_cuts(pautas, segments)
        # Deve minerar pelo menos 3 cortes virais distintos dentro dessa fala de 4 minutos
        self.assertGreaterEqual(len(cuts), 3)
        for c in cuts:
            self.assertGreaterEqual(c["duration_s"], 20.0)
            self.assertLessEqual(c["duration_s"], 85.0)

    def test_generate_viral_cut_metadata_empty_and_signature(self):
        from core.analyzer import (
            generate_viral_cut_metadata,
            generate_title_individual,
            generate_headline_individual,
            generate_description_individual,
            generate_hashtags_individual,
            generate_tags_seo_individual
        )
        # Transcrição vazia deve retornar estrutura com fallback sem quebrar
        meta = generate_viral_cut_metadata("", user_guidance="Tom urgente sobre eleições")
        self.assertIn("titulo_principal", meta)
        self.assertIn("descricao", meta)
        self.assertIn("hashtags", meta)
        self.assertIn("tags_seo", meta)

        # Teste de assinaturas aceitando user_guidance
        t = generate_title_individual("", user_guidance="Tom polêmico")
        self.assertIn("titulo_principal", t)
        hl = generate_headline_individual("", user_guidance="Curto e impactante")
        self.assertIn("headline_topo", hl)
        d = generate_description_individual("", user_guidance="Com CTA")
        self.assertIn("descricao", d)
        h = generate_hashtags_individual("", user_guidance="Tema política")
        self.assertIn("hashtags", h)
        s = generate_tags_seo_individual("", user_guidance="Palavras chave")
        self.assertIn("tags_seo", s)


if __name__ == '__main__':
    unittest.main()
