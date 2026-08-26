---
name: viralcut-qa-testing
description: >-
  Guia de qualidade, testes unitários com pytest, mocks para pipeline de vídeo/IA e regras de savepoint local no Git para o ViralCut.
---

# ViralCut: Garantia de Qualidade, Testes & Git Savepoints

Este guia estabelece os padrões de testes automatizados e integridade do código no ViralCut.

---

## 1. Suíte de Testes Automatizados com Pytest

- **Execução dos Testes**:
  ```bash
  d:\Repository\shorcut-factory\venv\Scripts\pytest tests/ -v
  ```
- **Localização dos Testes**: `tests/`
  - `test_analyzer_utils.py`: Funções utilitárias de tempo, títulos e segmentação.
  - `test_face_tracker.py`: Detecção de rostos, plano conjunto (Dual Shot) e auto-zoom.
  - `test_overlay_manager.py`: Modos de redimensionamento (`fill`, `fit`, `cover`), posicionamento e logo embutido.
  - `test_quick_editor.py`: Operações de trim, remoção de trechos e cálculo de duração.
  - `test_thumbnail_generator.py`: Geração de 3 variações de capa, CLAHE e conversões 9:16/16:9.
  - `test_retention_effects.py`: Barra de progresso, zoom punch, climax zoom e callouts.
  - `test_audio_mixer.py`: Ducking presets e busca de trilhas.
  - `test_config_manager.py`: Persistência e restauração de preferências.
  - `test_cuts_catalog.py`: Registro e exclusão de formatos no catálogo.
  - `test_export_kit.py`: Empacotamento viral de cortes.
  - `test_live_stream_handler.py`: Reconhecimento e metadados de transmissões ao vivo.

---

## 2. Boas Práticas para Criação de Testes Unitários

1. **Rapidez e Isolamento**:
   - Evite rodar processamento pesado de vídeos inteiros de 40 minutos em testes unitários. Crie mocks rápidos ou utilize frames sintéticos gerados pelo NumPy/OpenCV (`np.zeros((1080, 1920, 3), dtype=np.uint8)`).
2. **Cobertura Contínua**:
   - Todo novo módulo criado no `core/` deve vir acompanhado de seu respectivo arquivo em `tests/test_<modulo>.py`.
3. **100% de Aprovação**:
   - Nenhuma entrega é considerada concluída se algum teste falhar.

---

## 3. Regras de Ouro no Git

1. **Commit Local após cada Milestone**:
   - Utilize mensagens no padrão *Conventional Commits* (ex: `feat(overlay): ...`, `fix(ui): ...`, `docs: ...`).
2. **Push Remoto Protegido**:
   - **`git push` JAMAIS deve ser executado automaticamente pelo assistente.**
   - O assistente só deve realizar `git push` se o usuário solicitar expressamente com frases como *"faça o push"*, *"envie para o GitHub"* ou similar.
