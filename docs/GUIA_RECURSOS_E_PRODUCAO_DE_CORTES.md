# 🎬 ViralCut / Fábrica de Cortes — Guia Oficial de Recursos & Produção

> **Documento Executivo de Capacidades e Especificações Técnicas**  
> *Versão do Sistema: 2026.11 | Plataforma: ViralCut / Fábrica de Cortes*

---

## 📌 1. Visão Geral da Plataforma

O **ViralCut / Fábrica de Cortes** é uma esteira de produção automatizada de vídeos curtos em alta resolução para redes sociais (**YouTube Shorts, Instagram Reels, TikTok, Kwai e X**).

A plataforma cobre o ciclo completo de produção em 5 seções integradas:
1. **Ingestão Inteligente:** Captura de vídeos longos, transmissões ao vivo (lives) e uploads locais com garantia de resolução Full HD (1080p).
2. **Mineração & Roteirização:** Detecção de momentos virais via IA local (Ollama / Llama 3) ou importação de roteiros estruturados em JSON.
3. **Fábrica de Enquadramento:** Aplicação em lote ou individual de enquadramentos 9:16/16:9, legendas dinâmicas, headlines magnéticas, trilhas sonoras com ducking automático e selos sociais.
4. **Galeria de Cortes & Pós-Produção:** Catálogo centralizado de vídeos gerados, visualização lado a lado, ajuste de velocidade e download do pacote viral.
5. **Central de Publicação Multiplataforma:** Upload automatizado para YouTube Shorts, X/Twitter e integração com webhooks (n8n, Make, Zapier).

---

## 📥 2. Métodos de Ingestão e Criação de Cortes

| Método | Como Funciona | Melhor Utilização |
|---|---|---|
| **Roteiro JSON Externo** | Importação de arquivo JSON estruturado com minutagens, ranking, notas virais (1 a 10), gancho, textos âncora e enquetes. Permite corte a corte ou geração em lote com 1 clique. | Roteiros gerados por agentes de IA externos ou equipes de editores. |
| **Mineração por IA (Ollama / Llama 3)** | A IA analisa a transcrição completa do áudio, identifica ganchos de alta retenção e gera títulos virais e minutagens sugeridas automaticamente. | Vídeos longos de entrevistas, podcasts e palestras sem minutagem prévia. |
| **Carrossel Inteligente** | Fatiamento contínuo em $N$ partes iguais sem quebra de frases, mantendo a continuidade do raciocínio entre as partes. | Cortes sequenciais ("Parte 1", "Parte 2") para consumo em lista. |
| **Corte Cirúrgico Manual** | Definição milimétrica de tempo inicial e final (`HH:MM:SS.SS`) com suporte a player interativo e visualização de momentos mais assistidos (*Heatmap Hotspots*). | Trechos específicos conhecidos pelo criador de conteúdo. |

---

## 🎨 3. Recursos Aplicáveis ao Vídeo

### 3.1. Formatos e Enquadramentos de Imagem
- **9:16 Vertical Nativo:** Padrão das plataformas de vídeo vertical (1080x1920).
- **16:9 Horizontal Full HD:** Clipes panorâmicos clássicos com zoom digital e corte de bordas pretas (ROI Crop).
- **9:16 com Smart Blur (Fundo Desfocado):** Mantém o vídeo 16:9 centralizado e preenche as barras superior e inferior com o próprio vídeo ampliado em desfoque gaussiano suave.
- **Auto-Zoom Inteligente no Personagem (MediaPipe BlazeFace):** Rastreia e enquadra o rosto do interlocutor em movimento contínuo, com margem de segurança configurável para evitar cortes na cabeça.
- **Split Screen (Câmera Dupla):** Divide a tela vertical em duas metades (topo e rodapé) para enquadrar simultaneamente dois oradores de uma conversa ou debate.
- **Auto-Switching de Câmera (Multicam):** Alterna o foco da câmera dinamicamente entre os participantes com base em quem está falando.
- **Split com Mídia Secundária / Slideshow:** Insere um vídeo secundário (ex: gameplay de retenção ou carrossel de fotos/produtos) na metade complementar da tela.

### 3.2. Legendas Dinâmicas & Tradução
- **Sincronia Palavra por Palavra (*Word-Level Timing*):** Transcrição de alta precisão via Whisper ou extração oficial do YouTube.
- **Destaque Estilo Karaokê (*Highlight Color*):** A palavra falada ganha cor vibrante de destaque (amarelo, verde neon, ciano) no instante exato da pronúncia.
- **Tipografia e Legibilidade:** Fonte com traço de contorno (*stroke*) e sombra projetada garantindo legibilidade sobre qualquer fundo.
- **Tradução Automática de Legendas:** Tradução em tempo real do áudio para outros idiomas (ex: Português $\rightarrow$ Inglês / Espanhol) antes da renderização.

### 3.3. Retenção & Elementos Gráficos
- **Headline de Topo Magnética:** Caixa de gancho visual fixada no topo do vídeo 9:16 com texto curto e impactante.
  - *Presets visuais:* Caixa sólida, texto contornado, *Connected Bubble* (balão de comentário), etc.
  - *Efeitos de entrada:* Estático, *Slide* suave ou *Explosão*.
- **Barra de Progresso Temporal:** Linha animada no rodapé que avança com a reprodução do vídeo para maximizar o tempo de retenção.
- **Zoom Punch & Clímax Zoom:** Ampliação súbita em momentos-chave e aceleração no final para reforçar a conclusão.
- **Callout / CTA Flutuante:** Chamada para ação temporizada incentivando a inscrição ou o debate nos comentários.

### 3.4. Engenharia de Áudio
- **Trilha Sonora de Fundo (BGM):** Mixagem de faixas musicais livres de royalties ou trilhas enviadas pelo usuário.
- **Sidechain Audio Ducking Automático:** O volume da música é atenuado de forma automática e suave sempre que a voz é detectada, voltando a subir nas pausas.
- **Normalização e Equalização:** Áudio tratado para atender aos limites de sonoridade (*loudness*) das redes sociais, sem distorção.

### 3.5. Assinatura de Redes Sociais (@Handle Overlay)
- **Selo de Identidade Visual:** Pílula gráfica com ícone da rede (Instagram, TikTok, YouTube Shorts, X, Kwai) e o `@arroba` do canal.
- **Posicionamento Flexível:** Margens configuráveis (topo, centro, rodapé, alinhado à esquerda ou à direita).

### 3.6. Capas & Thumbnails Automáticas
- **Seleção por Nitidez (*Sharpness Detection*):** Algoritmo de visão computacional analisa os frames do corte e seleciona as imagens mais nítidas, evitando expressões desfavoráveis ou rostos borrados.
- **Exportação Imediata:** Gera `thumbnail.jpg` pronta na resolução nativa do formato escolhido.

---

## 📦 4. Estrutura do Pacote Viral Gerado

Para cada corte processado, a aplicação gera uma pasta estruturada autossuficiente contendo:

```
data/[video_id]/[corte_format_timestamp]/
├── video.mp4               # Vídeo Full HD final com aceleração NVENC/FFmpeg
├── thumbnail.jpg           # Capa de alta resolução para o feed
├── legendas.srt            # Arquivo de legendas externas sincronizadas
├── transcricao_corte.txt   # Transcrição integral do trecho em texto puro
├── transcricao_corte.json  # Transcrição detalhada com timestamps
└── metadados.json          # Metadados completos do projeto
```

### Metadados e Textos Gerados:
- **Título Viral:** Título principal otimizado para cliques.
- **Títulos Alternativos:** Variações sugeridas para testes A/B.
- **Descrição Completa:** Contextualização com chamada para ação (CTA).
- **Hashtags Estratégicas:** Conjunto balanceado de hashtags de nicho e tendências.
- **Tags SEO:** Lista de palavras-chave para mecanismos de busca.
- **Enquetes / Perguntas de Engajamento:** Questão pronta para fixar no primeiro comentário ou na aba comunidade.

---

## 🚀 5. Canais de Distribuição e Publicação

- **Galeria de Cortes & Pós (Aba 4):** Central de reprodução, comparação de resoluções e download direto de arquivos ou abertura no Windows Explorer.
- **YouTube Shorts:** Publicação nativa via API oficial com escolha de visibilidade (*Público*, *Não Listado*, *Privado*).
- **X (antigo Twitter):** Postagem de vídeo nativo acompanhado do texto formatado e hashtags.
- **Webhooks de Automação:** Despacho de payload padronizado em JSON para plataformas de automação (**n8n, Make, Zapier**), viabilizando autopost no Instagram Reels, TikTok e Telegram.

---

## 📋 6. Resumo das Capacidades

| Categoria | Recurso | Disponível Hoje |
|---|---|:---:|
| **Ingestão** | YouTube (Vídeos & Lives ao Vivo) | ✅ |
| **Ingestão** | Kick.com, Twitter/X, Instagram, TikTok, Arquivo Local | ✅ |
| **Resolução** | Garantia Full HD (1080p) com EJS Solver e Deno | ✅ |
| **Roteirização** | Importação de Roteiro JSON Externo com Ranking | ✅ |
| **Roteirização** | Mineração por IA Local (Ollama / Llama 3) | ✅ |
| **Roteirização** | Fatiamento Contínuo para Carrossel | ✅ |
| **Automação** | Geração em Lote em Sequência de Todos os Cortes do JSON | ✅ |
| **Enquadramento** | 9:16 Vertical, 16:9 Horizontal, Smart Blur | ✅ |
| **Enquadramento** | Auto-Zoom Facial (MediaPipe BlazeFace) | ✅ |
| **Enquadramento** | Split Screen (Câmera Dupla) & Multicam Auto-Switch | ✅ |
| **Enquadramento** | Split com Mídia Secundária (Gameplay / Slideshow) | ✅ |
| **Legendas** | Karaokê Dinâmico com Highlight Palavra por Palavra | ✅ |
| **Legendas** | Tradução Automática Multi-idioma | ✅ |
| **Retenção** | Headline de Topo Magnética com Presets de Cores e Estilos | ✅ |
| **Retenção** | Barra de Progresso, Zoom Punch e Clímax Zoom | ✅ |
| **Áudio** | Trilha Sonora com Sidechain Audio Ducking Automático | ✅ |
| **Branding** | Assinatura de Redes Sociais (@Handle Overlay) | ✅ |
| **Capas** | Geração de Thumbnails Inteligentes por Nitidez | ✅ |
| **Exportação** | Pacote Viral Completo (.mp4, .srt, .txt, .json, capa) | ✅ |
| **Publicação** | YouTube Shorts & X Diretos via API | ✅ |
| **Publicação** | Webhook para n8n, Make e Zapier | ✅ |

---
*Documento gerado automaticamente pelo ViralCut — Sistema Integrado de Produção de Mídia Curta.*

