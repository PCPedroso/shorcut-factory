# 🚀 Guia Oficial de Configuração — Central de Publicação Multiplataforma
> **ViralCut Studio** — Esteira de Postagem Nativa para YouTube Shorts, Instagram Reels, TikTok, X (Twitter) e Kwai.

Este documento fornece o passo a passo completo e todos os links oficiais para obter as chaves de acesso (APIs) gratuitas de cada rede social e configurar a **Central de Publicação (Seção 5)**.

---

## 🔒 Segurança & Cofre de Credenciais (DPAPI)
Todas as chaves, tokens e segredos informados na aplicação são **criptografados diretamente no nível do sistema operacional Windows** usando a API nativa **Windows DPAPI** (`CryptProtectData`), vinculados estritamente à sua conta de usuário do Windows.
- O arquivo criptografado fica armazenado localmente em `data/publishing_credentials.enc`.
- Nenhum token trafega em texto puro ou é compartilhado com terceiros.

---

## 📸 1. Instagram Reels (Meta Graph API v20.0)

A publicação oficial no Instagram utiliza a API oficial da Meta para contas profissionais (**Criador de Conteúdo** ou **Comercial**). É 100% gratuita.

### 🔗 Links Oficiais
- **Painel de Desenvolvedores Meta**: [https://developers.facebook.com/](https://developers.facebook.com/)
- **Ferramenta de Geração de Tokens (Graph API Explorer)**: [https://developers.facebook.com/tools/explorer/](https://developers.facebook.com/tools/explorer/)
- **Documentação Oficial de Reels Publishing**: [Meta Content Publishing Guide](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/content-publishing)

---

### 📋 Pré-requisitos (Gratuitos)
1. **Conta Profissional no Instagram**:
   - No celular, abra o Instagram $\to$ *Configurações $\to$ Tipo de conta e ferramentas $\to$ Mudar para conta profissional* (escolha **Criador de Conteúdo** ou **Empresa**).
2. **Página do Facebook Vinculada**:
   - Vincule sua conta do Instagram a qualquer Página do Facebook que você administre (pode criar uma página nova e vazia no Facebook em 1 minuto caso não tenha).

---

### 🔑 Passo a Passo para Gerar as Credenciais

#### Passo 1.1: Criar o Aplicativo no Meta Developers
1. Acesse [developers.facebook.com](https://developers.facebook.com/) e faça login com seu Facebook.
2. Clique em **Meus Aplicativos** (canto superior direito) $\to$ **Criar Aplicativo**.
3. Selecione o caso de uso: **Outro** (ou **Empresa**) e avance.
4. Tipo de app: selecione **Empresa** ou **Consumidor** $\to$ Dê um nome (ex: `ViralCut Publicador`) $\to$ Concluir.

#### Passo 1.2: Gerar o Access Token no Graph API Explorer
1. Acesse o [Graph API Explorer](https://developers.facebook.com/tools/explorer/).
2. No menu superior direito:
   - Em **Aplicativo do Meta**, selecione o aplicativo criado (`ViralCut Publicador`).
   - Em **Usuário ou página**, selecione seu usuário.
3. No painel **Permissões (Permissions)**, clique em *Adicionar uma permissão* e inclua as 4 seguintes:
   - `instagram_basic`
   - `instagram_content_publish`
   - `pages_show_list`
   - `pages_read_engagement`
4. Clique no botão azul **Generate Access Token** e confirme a autorização na tela da Meta.

#### Passo 1.3: Descobrir o seu `ig_user_id` (ID da Conta do Instagram)
No próprio Graph API Explorer, no campo de query central:
1. Digite e execute:
   ```http
   GET /me/accounts
   ```
   Copie o `id` da Página que aparecer no retorno.
2. Em seguida, digite e execute (substituindo pelo seu ID de página):
   ```http
   GET /{id_da_sua_pagina}?fields=instagram_business_account
   ```
3. O número exibido no campo `"id"` dentro de `"instagram_business_account"` é o seu **`ig_user_id`**.

#### Passo 1.4: Inserir no ViralCut Studio
1. Na aplicação, acesse a aba **`5. 🚀 Central de Publicação`**.
2. No card **📸 Instagram Reels**, clique em **Configurar Instagram Reels**.
3. Cole:
   - **User/Page Access Token**: O token gerado no Explorer.
   - **Instagram Account ID (ig_user_id)**: O ID numérico descoberto acima.
   - **Nome de Usuário (@)**: Seu arroba no Instagram (ex: `meucanaldecortes`).
4. Clique em **Salvar Credenciais Instagram**. O status mudará imediatamente para **🟢 Conectado**.

---

## 🔴 2. YouTube Shorts (YouTube Data API v3)

A publicação no YouTube Shorts utiliza OAuth 2.0 nativo e upload em blocos resumable (8MB por chunk). É 100% gratuita com cota diária de 10.000 unidades (suficiente para ~6 Shorts por dia).

### 🔗 Links Oficiais
- **Google Cloud Console**: [https://console.cloud.google.com/](https://console.cloud.google.com/)
- **Biblioteca da YouTube Data API v3**: [Ativar YouTube Data API v3](https://console.cloud.google.com/apis/library/youtube.googleapis.com)
- **Credenciais OAuth Google Cloud**: [Criar Credenciais OAuth](https://console.cloud.google.com/apis/credentials)

---

### 🔑 Passo a Passo para Gerar o `client_secrets.json`

1. Acesse o [Google Cloud Console](https://console.cloud.google.com/).
2. Crie um novo projeto (ex: `ViralCut Studio`).
3. Vá em **APIs e Serviços** $\to$ **Biblioteca** $\to$ pesquise por `YouTube Data API v3` $\to$ clique em **Ativar**.
4. Configure a **Tela de Permissão OAuth** (OAuth Consent Screen):
   - Tipo de usuário: **Externo** $\to$ Criar.
   - Nome do app: `ViralCut` $\to$ Informe seu e-mail de suporte $\to$ Salvar e continuar.
   - Em **Usuários de Teste (Test Users)**: Adicione o seu próprio e-mail do Google (o mesmo dono do canal do YouTube onde você postará).
5. Vá em **Credenciais** $\to$ **+ Criar Credenciais** $\to$ **ID do cliente OAuth**:
   - Tipo de aplicativo: **Aplicativo para computador (Desktop App)**.
   - Nome: `ViralCut Desktop`.
   - Clique em **Criar**.
6. Clique no ícone de download (⬇️) ao lado da credencial gerada para baixar o arquivo JSON.
7. Renomeie o arquivo baixado para **`client_secrets.json`** e salve-o na pasta raiz do projeto (`d:\Repository\shorcut-factory\client_secrets.json`).
8. Na Central de Publicação do ViralCut, no card do YouTube, clique em **Autenticar Canal YouTube**. Seu navegador abrirá a tela do Google para você autorizar o canal com 1 clique!

---

## 🎵 3. TikTok (TikTok Content Posting API v2)

Permite publicação direta ou envio para os **Rascunhos Privados (`SELF_ONLY`)** na sua caixa de entrada do aplicativo TikTok.

### 🔗 Links Oficiais
- **Portal de Desenvolvedores TikTok**: [https://developers.tiktok.com/](https://developers.tiktok.com/)
- **Documentação da Content Posting API v2**: [TikTok Content Posting Guide](https://developers.tiktok.com/doc/content-posting-api-get-started)

---

### 🔑 Passo a Passo
1. Acesse o [TikTok for Developers](https://developers.tiktok.com/) e faça login com sua conta do TikTok.
2. Clique em **Manage Apps** $\to$ **Create an App**.
3. Adicione o produto **Content Posting API** com as permissões:
   - `video.publish` (publicação direta)
   - `video.upload` (envio para rascunhos da caixa de entrada)
4. Obtenha seu **Access Token** e **OpenID** do usuário no painel do app.
5. Na aba **5. 🚀 Central de Publicação** do ViralCut, abra o configurador do TikTok, cole o **Access Token** e o **Open ID** e salve.
   > **Dica ViralCut**: Na tela de disparo, recomendamos manter o status de privacidade como **Rascunho Privado (`SELF_ONLY`)**. O corte aparecerá imediatamente no seu aplicativo móvel do TikTok para você dar o toque final com áudios em alta antes de torná-lo público.

---

## ✖️ 4. X (antigo Twitter) — Modo Gratuito vs Modo API

O X alterou as regras da API de vídeo (o upload de vídeo requer o plano pago Basic de US$ 100/mês). Por isso, o ViralCut Studio implementa **duas opções flexíveis**:

### 💡 Opção A: Modo Manual Assistido (100% Gratuito — Recomendado)
- **Não requer pagamento, nem cadastro de desenvolvedor.**
- Ao disparar o corte:
  1. O texto adaptado (respeitando rigorosamente o limite de 280 caracteres e URLs) é copiado para sua Área de Transferência (**Ctrl+V**).
  2. O vídeo MP4 pronto é automaticamente destacado no **Windows Explorer**.
  3. A janela de postagem do X ([https://x.com/compose/post](https://x.com/compose/post)) é aberta no seu navegador.
  4. Basta arrastar o vídeo e pressionar Ctrl+V no texto.
- **Como ativar**: Na Central de Publicação, em **Configurar X (Twitter)**, marque **📋 Modo Manual Assistido** e clique em salvar.

### 🔑 Opção B: API Automática (Para quem possui chaves Developer)
- **Portal de Desenvolvedores X**: [https://developer.x.com/en/portal/dashboard](https://developer.x.com/en/portal/dashboard)
- Requer informar: `API Key`, `API Secret`, `Access Token`, `Access Token Secret` (OAuth 1.0a) ou `Bearer Token` (OAuth 2.0).

---

## 🟠 5. Kwai Creator (Exportação Assistida Nativa)

O Kwai não possui API pública aberta para criadores independentes (apenas para campanhas pagas de agências de publicidade). Tentativas de automação por navegadores fantasmas (Puppeteer/Playwright) geram bloqueios severos de IP e CAPTCHA de quebra-cabeça.

### 🔗 Link Oficial
- **Painel Kwai Creator Web**: [https://creator.kwai.com/](https://creator.kwai.com/)

---

### ⚡ Como Funciona no ViralCut (Zero Configuração)
O módulo do Kwai está **sempre ativo (🟢 Conectado)** e não necessita de nenhuma chave ou token:
1. Valida automaticamente a resolução 9:16 e duração do vídeo.
2. Adapta a legenda para o estilo Kwai com hashtags virais (limite de 500 caracteres).
3. Copia a legenda para o Clipboard do Windows via utilitário nativo `clip.exe`.
4. Abre o arquivo de vídeo pronto no Windows Explorer.
5. Abre o [Kwai Creator Web](https://creator.kwai.com/) no seu navegador padrão para você fazer o upload rápido com 1 clique.

---

## 📊 Matriz Comparativa de Especificações Técnicas

| Rede Social | Formato / Aspect Ratio | Codec de Vídeo | Codec de Áudio | Duração Máxima | Limite de Caracteres |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **YouTube Shorts** | 9:16 (1080x1920) | H.264 / MP4 | AAC (48kHz) | 60 segundos | 100 caracteres no título (`#Shorts`) |
| **Instagram Reels** | 9:16 (1080x1920) | H.264 / MP4 | AAC (48kHz) | 90 segundos | 2.200 caracteres (até 30 hashtags) |
| **TikTok** | 9:16 (1080x1920) | H.264 / MP4 | AAC (48kHz) | 10 minutos | 2.200 caracteres |
| **X (Twitter)** | 9:16 ou 16:9 | H.264 / MP4 | AAC (48kHz) | 140 segundos | 280 caracteres |
| **Kwai** | 9:16 (1080x1920) | H.264 / MP4 | AAC (48kHz) | 15 minutos | 500 caracteres |

---

## 🛠️ Solução de Dúvidas Rápidas (FAQ)

### O upload falhou com erro de token expirado no Instagram?
Os tokens de curta duração do Graph API Explorer duram 1 a 2 horas. No painel de configuração do Instagram no ViralCut, você pode utilizar um token de longa duração (Long-Lived Token), que permanece válido por 60 dias e pode ser renovado com 1 clique antes do vencimento.

### O vídeo demorou para aparecer como publicado?
O Instagram e o TikTok realizam o encode nos próprios servidores em segundo plano após o recebimento dos bytes. A Central de Publicação do ViralCut inclui polling inteligente: o worker daemon aguarda a finalização oficial do processamento na nuvem da rede antes de marcar o status como **PUBLISHED** e liberar o link direto para você assistir online.
