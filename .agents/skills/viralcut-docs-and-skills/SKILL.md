---
name: viralcut-docs-and-skills
description: >-
  Guia para manter a documentação mestre (Fábrica de Cortes.md), transições de fases do roadmap e evolução contínua das skills e arquitetura do projeto ViralCut.
---

# ViralCut: Governança de Documentação e Manutenção de Skills

Esta skill orienta o processo de manutenção da documentação do projeto, transição de fases do roadmap e evolução das skills do assistente.

---

## 1. Documento Mestre: `Fábrica de Cortes.md`

O arquivo `Fábrica de Cortes.md` deve ser mantido sempre atualizado e estruturado nas seguintes seções:

1. **Visão Geral e Objetivos do Sistema**: Propósito do ViralCut e público-alvo.
2. **Arquitetura Técnica do Pipeline**: Fluxo ponta a ponta (Download -> Transcrição -> Análise -> Rastreamento -> Efeitos/Overlays -> Renderização -> Empacotamento).
3. **Mapeamento de Arquivos e Responsabilidades (`core/`)**: Cada módulo Python documentado com suas funções principais e fluxos.
4. **Status do Projeto por Fase**: Detalhamento das funcionalidades implementadas e prontas para uso.
5. **Roadmap de Evolução Futura**: Fases futuras (Fase 5 - SFX/B-Roll, Fase 6 - Automação Total) com escopo bem definido.
6. **Diretrizes e Regras do Projeto**: Regras de Git, hardware e ambiente.

### Checklist de Atualização da Documentação:
- [ ] Nova funcionalidade implementada e testada com 100% de aprovação na suíte de testes.
- [ ] Módulo e função documentados no Mapeamento de Arquivos.
- [ ] Tópico detalhado na seção da respectiva Fase no `Fábrica de Cortes.md`.
- [ ] Contagem de testes automatizados atualizada.
- [ ] Savepoint local (`git commit`) registrado.

---

## 2. Manutenção e Evolução das Skills (`.agents/skills/`)

Quando um novo domínio técnico ou biblioteca for adicionado ao projeto:
1. Verifique se o conhecimento se enquadra em uma das skills existentes (`video-pipeline`, `face-tracking`, `ai-mining`, `audio-sfx`, `ui-gallery`, `qa-testing`).
2. Caso seja um padrão recorrente ou nova fase (ex: B-Roll Engine, Agendador de Postagens), crie ou atualize o respectivo `SKILL.md`.
3. Garanta que o frontmatter YAML contenha `name` e uma `description` clara e rica em palavras-chave para acionamento contextual preciso.
