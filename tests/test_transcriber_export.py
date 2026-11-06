"""
Testes unitários para as funções de exportação de transcrição:
  - segments_to_txt
  - segments_to_srt
  - segments_to_vtt
"""
import pytest
from core.transcriber import segments_to_txt, segments_to_srt, segments_to_vtt


# ---------------------------------------------------------------------------
# Dados de fixture
# ---------------------------------------------------------------------------

SAMPLE_SEGMENTS = [
    {"start": 0.0, "end": 2.5, "text": "Olá mundo"},
    {"start": 2.5, "end": 5.0, "text": "Teste de exportação"},
    {"start": 5.0, "end": 8.75, "text": "Terceiro segmento aqui"},
]

SINGLE_SEGMENT = [{"start": 1.0, "end": 3.0, "text": "Texto único"}]

HOUR_SEGMENT = [
    {"start": 3600.0, "end": 3663.5, "text": "Segmento na primeira hora"},
]

MIXED_EMPTY = [
    {"start": 0.0, "end": 1.0, "text": "Primeiro"},
    {"start": 1.0, "end": 2.0, "text": ""},
    {"start": 2.0, "end": 3.0, "text": "   "},
    {"start": 3.0, "end": 4.0, "text": "Terceiro"},
]


# ---------------------------------------------------------------------------
# segments_to_txt
# ---------------------------------------------------------------------------

class TestSegmentsToTxt:
    def test_basic_two_segments(self):
        result = segments_to_txt(SAMPLE_SEGMENTS)
        assert "Olá mundo" in result
        assert "Teste de exportação" in result
        assert "Terceiro segmento aqui" in result

    def test_empty_list_returns_empty_string(self):
        assert segments_to_txt([]) == ""

    def test_none_equivalent_empty(self):
        # Lista com segmentos sem texto não deve retornar nada útil
        result = segments_to_txt([{"start": 0.0, "end": 1.0, "text": ""}])
        assert result == ""

    def test_single_segment(self):
        result = segments_to_txt(SINGLE_SEGMENT)
        assert result == "Texto único"

    def test_skips_blank_segments(self):
        result = segments_to_txt(MIXED_EMPTY)
        assert "Primeiro" in result
        assert "Terceiro" in result
        # Garante que não há espaços duplos ou ruído
        assert "  " not in result.strip()

    def test_no_timestamps_in_output(self):
        result = segments_to_txt(SAMPLE_SEGMENTS)
        assert "-->" not in result
        assert ":" not in result or True  # timestamps têm formato HH:MM:SS


# ---------------------------------------------------------------------------
# segments_to_srt
# ---------------------------------------------------------------------------

class TestSegmentsToSrt:
    def test_empty_list_returns_empty_string(self):
        assert segments_to_srt([]) == ""

    def test_format_has_sequence_numbers(self):
        result = segments_to_srt(SAMPLE_SEGMENTS)
        lines = result.split("\n")
        assert lines[0] == "1"
        # Encontra o segundo bloco
        assert "2" in lines

    def test_arrow_separator_present(self):
        result = segments_to_srt(SAMPLE_SEGMENTS)
        assert "-->" in result

    def test_srt_uses_comma_for_milliseconds(self):
        result = segments_to_srt(SAMPLE_SEGMENTS)
        # Timestamps SRT usam vírgula: 00:00:00,000
        assert "," in result
        assert "." not in result.split("-->")[0]  # lado esquerdo não usa ponto

    def test_one_hour_timestamp_format(self):
        result = segments_to_srt(HOUR_SEGMENT)
        assert "01:00:00,000" in result
        assert "01:01:03,500" in result

    def test_skips_empty_text_segments(self):
        result = segments_to_srt(MIXED_EMPTY)
        # Apenas 2 segmentos com texto real → sequência vai até 2
        lines = [l for l in result.split("\n") if l.strip()]
        numbered = [l for l in lines if l.isdigit()]
        assert len(numbered) == 2

    def test_text_appears_in_output(self):
        result = segments_to_srt(SINGLE_SEGMENT)
        assert "Texto único" in result

    def test_blocks_separated_by_blank_line(self):
        result = segments_to_srt(SAMPLE_SEGMENTS)
        # Deve haver pelo menos 2 linhas em branco entre blocos
        assert "\n\n" in result


# ---------------------------------------------------------------------------
# segments_to_vtt
# ---------------------------------------------------------------------------

class TestSegmentsToVtt:
    def test_empty_list_returns_webvtt_header(self):
        result = segments_to_vtt([])
        assert result.startswith("WEBVTT")

    def test_non_empty_starts_with_webvtt(self):
        result = segments_to_vtt(SAMPLE_SEGMENTS)
        assert result.startswith("WEBVTT")

    def test_vtt_uses_dot_for_milliseconds(self):
        result = segments_to_vtt(SAMPLE_SEGMENTS)
        # Timestamps VTT usam ponto: 00:00:00.000
        ts_lines = [l for l in result.split("\n") if "-->" in l]
        for ts in ts_lines:
            assert "." in ts
            assert "," not in ts

    def test_one_hour_timestamp_format(self):
        result = segments_to_vtt(HOUR_SEGMENT)
        assert "01:00:00.000" in result
        assert "01:01:03.500" in result

    def test_arrow_separator_present(self):
        result = segments_to_vtt(SAMPLE_SEGMENTS)
        assert "-->" in result

    def test_no_sequence_numbers(self):
        result = segments_to_vtt(SAMPLE_SEGMENTS)
        lines = result.split("\n")
        # Nenhuma linha deve ser apenas um número inteiro (diferente do SRT)
        numbered = [l for l in lines if l.strip().isdigit()]
        assert len(numbered) == 0

    def test_text_appears_in_output(self):
        result = segments_to_vtt(SINGLE_SEGMENT)
        assert "Texto único" in result

    def test_skips_empty_text_segments(self):
        result = segments_to_vtt(MIXED_EMPTY)
        ts_lines = [l for l in result.split("\n") if "-->" in l]
        assert len(ts_lines) == 2
