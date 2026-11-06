"""
Testes unitários para importação e registro de cortes via JSON:
  - parse_json_cuts
  - register_cuts_from_parsed
"""

import os
import json
import pytest
from core.cuts_catalog import (
    parse_json_cuts, register_cuts_from_parsed, _raw_load_cuts_catalog, make_time_key
)


SAMPLE_JSON = {
    "schema_version": "1.0",
    "etapa": "textos",
    "video": {
        "url": "https://youtu.be/jxWeG0eSVCg",
        "idioma": "pt-BR",
        "duracao_aproximada": "00:28:15.00"
    },
    "resumo": "Comentário sobre taxa de juro real e Selic.",
    "cortes": [
        {
            "id": "C2",
            "inicio": "00:05:12.00",
            "fim": "00:07:24.50",
            "frase_inicio": "O governo Lula, ele consegue...",
            "frase_fim": "...fica muito mais complicado.",
            "descricao": "Argumenta sobre meta de inflação.",
            "gancho": "Quer ver eu te provar?",
            "potencial_viralizacao": {"nota": 8, "justificativa": "Gancho forte."},
            "depende_visual": False,
            "risco_contexto": "alto",
            "observacoes": [{"tipo": "contexto", "texto": "Debate prévio."}],
            "duracao_segundos": 132.5,
            "duracao_formatada": "00:02:12.50",
            "textos": {
                "titulos": [
                    {"texto": "Quem decide a meta de inflação?", "caracteres": 31},
                    {"texto": "Governo pode mudar a meta?", "caracteres": 27}
                ],
                "descricao": {
                    "texto": "Segundo o apresentador...",
                    "hashtags": ["#inflacao", "economia", "#bancocentral"],
                    "credito": "Fonte: Canal X"
                },
                "textos_ancora": [
                    {"texto": "Quem decide a meta?", "tipo": "padrao"}
                ],
                "enquete": {
                    "texto": "Mudar a meta?",
                    "opcoes": ["Sim", "Não"]
                }
            }
        },
        {
            "id": "C6",
            "inicio": "00:19:34.50",
            "fim": "00:21:51.00",
            "frase_inicio": "Olha só, descontando a inflação...",
            "frase_fim": "...problema com moeda.",
            "descricao": "Mostra ranking de juro real.",
            "gancho": "O Brasil tem a maior taxa de juro real do planeta.",
            "potencial_viralizacao": {"nota": 9, "justificativa": "Dado forte."},
            "depende_visual": True,
            "risco_contexto": "medio",
            "observacoes": [{"tipo": "visual", "texto": "Tabela na tela."}],
            "duracao_segundos": 136.5,
            "duracao_formatada": "00:02:16.50",
            "textos": {
                "titulos": [
                    {"texto": "Juro real de 9,49%: por que o dólar não cai?", "caracteres": 46},
                    {"texto": "Brasil tem o maior juro real.", "caracteres": 29}
                ],
                "descricao": {
                    "texto": "Descontada a inflação...",
                    "hashtags": ["#juros", "#selic"],
                    "credito": "Fonte: Canal X"
                }
            }
        },
        {
            "id": "C3",
            "inicio": "00:08:38.00",
            "fim": "00:11:13.00",
            "descricao": "Compara Brasil e Turquia.",
            "gancho": "Baixar juros na marra.",
            "potencial_viralizacao": 9,
            "depende_visual": True,
            "risco_contexto": "medio",
            "textos": {
                "titulos": ["Baixar juros na marra?"]
            }
        }
    ],
    "ranking": [
        {"posicao": 1, "id": "C6", "ponderacao": "Dado forte e pergunta intrigante."},
        {"posicao": 2, "id": "C3", "ponderacao": "Mais didático."},
        {"posicao": 3, "id": "C2", "ponderacao": "Gancho forte."}
    ],
    "alertas_gerais": ["Legendas contêm erros; conferir valores."]
}


class TestJsonImportParser:
    def test_parse_json_cuts_basic(self):
        parsed = parse_json_cuts(SAMPLE_JSON)
        assert parsed["video_id"] == "jxWeG0eSVCg"
        assert parsed["video_url"] == "https://youtu.be/jxWeG0eSVCg"
        assert len(parsed["cortes"]) == 3
        assert len(parsed["alertas_gerais"]) == 1
        assert "Legendas contêm erros" in parsed["alertas_gerais"][0]

    def test_parse_json_cuts_ordering_by_ranking(self):
        parsed = parse_json_cuts(SAMPLE_JSON)
        cortes = parsed["cortes"]
        # Ranking especifica C6 como 1, C3 como 2, C2 como 3
        assert cortes[0]["id"] == "C6"
        assert cortes[0]["ranking_posicao"] == 1
        assert cortes[1]["id"] == "C3"
        assert cortes[1]["ranking_posicao"] == 2
        assert cortes[2]["id"] == "C2"
        assert cortes[2]["ranking_posicao"] == 3

    def test_parse_json_cuts_title_mapping(self):
        parsed = parse_json_cuts(SAMPLE_JSON)
        c6 = next(c for c in parsed["cortes"] if c["id"] == "C6")
        assert c6["title"] == "Juro real de 9,49%: por que o dólar não cai?"
        assert len(c6["alt_titles"]) == 1
        assert c6["alt_titles"][0] == "Brasil tem o maior juro real."

    def test_parse_json_cuts_hashtags(self):
        parsed = parse_json_cuts(SAMPLE_JSON)
        c2 = next(c for c in parsed["cortes"] if c["id"] == "C2")
        # 'economia' sem hash deve ser normalizado com '#'
        assert "#economia" in c2["hashtags"]
        assert "#inflacao" in c2["hashtags"]
        assert "#bancocentral" in c2["hashtags"]

    def test_parse_json_cuts_missing_textos(self):
        minimal_json = {
            "video": {"url": "https://www.youtube.com/watch?v=11223344556"},
            "cortes": [
                {
                    "id": "C1",
                    "inicio": "00:01:00.00",
                    "fim": "00:02:00.00",
                    "descricao": "Corte de teste sem textos."
                }
            ]
        }
        parsed = parse_json_cuts(minimal_json)
        assert len(parsed["cortes"]) == 1
        c1 = parsed["cortes"][0]
        assert c1["title"] == "Corte C1"
        assert c1["description"] == "Corte de teste sem textos."
        assert c1["hashtags"] == []

    def test_parse_json_cuts_invalid_schema(self):
        assert parse_json_cuts({})["cortes"] == []
        assert parse_json_cuts(None)["cortes"] == []
        assert parse_json_cuts("not-a-dict")["cortes"] == []


class TestRegisterCutsFromParsed:
    def test_register_cuts_creates_catalog_entries(self, tmp_path, monkeypatch):
        # Redireciona a pasta data para tmp_path
        test_video_id = "test_vid_123"
        cat_file = tmp_path / "data" / test_video_id / "cuts_catalog.json"

        # Monkeypatch _get_catalog_path para usar tmp_path
        monkeypatch.setattr(
            "core.cuts_catalog._get_catalog_path",
            lambda vid: str(tmp_path / "data" / vid / "cuts_catalog.json")
        )

        parsed = parse_json_cuts(SAMPLE_JSON)
        count = register_cuts_from_parsed(test_video_id, parsed)

        assert count == 3
        assert cat_file.exists()

        cat = json.loads(cat_file.read_text(encoding="utf-8"))
        # Verifica se as chaves de minutagem foram criadas
        assert len(cat) == 3

        # Verifica corte C6
        key_c6 = make_time_key("00:19:34.50", "00:21:51.00")
        assert key_c6 in cat
        item_c6 = cat[key_c6]
        assert item_c6["title"] == "Juro real de 9,49%: por que o dólar não cai?"
        assert item_c6["headline"] == "O Brasil tem a maior taxa de juro real do planeta."
        assert item_c6["json_cut_id"] == "C6"
        assert item_c6["ranking_posicao"] == 1
        assert item_c6["potencial_viralizacao"]["nota"] == 9
