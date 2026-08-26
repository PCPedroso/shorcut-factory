# Diretrizes & Regras do Projeto ViralCut / Fábrica de Cortes

## 1. Documentação Mestre Viva
- O arquivo `Fábrica de Cortes.md` na raiz do projeto é a **fonte única da verdade** sobre a arquitetura, status de funcionalidades, roadmap e decisões técnicas.
- **Regra**: Sempre que uma nova funcionalidade, ajuste arquitetural ou alteração relevante for implementada e testada, o arquivo `Fábrica de Cortes.md` deve ser atualizado.

## 2. Governança do Git
- **Savepoints Locais**: Realize commits atômicos no Git (`git add`, `git commit -m "..."`) para cada etapa concluída e testada.
- **Regra Crítica de Push**: **NUNCA execute `git push` automaticamente.** O push para o repositório remoto deve ser realizado **SOMENTE sob solicitação explícita do usuário**.

## 3. Ambiente e Execução
- **Sistema Operacional**: Windows 11 com PowerShell.
- **Ambiente Virtual**: `d:\Repository\shorcut-factory\venv`. Sempre utilize o Python e ferramentas instaladas nesse ambiente (`venv\Scripts\python.exe`, `venv\Scripts\pytest`).
- **Hardware**: Intel Core i5-9400F, 32 GB RAM, NVIDIA GeForce GTX 1650 (4 GB VRAM).
- **Aceleração**: Priorizar encoder GPU (`h264_nvenc`) para renderizações e modelos leves/médios para VRAM limitada.

## 4. Qualidade e Testes Contínuos
- Antes de concluir qualquer tarefa de código, execute a suíte de testes (`pytest tests/ -v`) e garanta 100% de aprovação.
- Sempre crie testes unitários para novos módulos ou regras de negócio críticas.
