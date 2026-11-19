# 🤖 Agente Pessoal Financeiro no WhatsApp

Este projeto implementa um **Agente Inteligente de Finanças Pessoais e PJ** integrado diretamente ao **WhatsApp**, conectado à sua planilha financeira no Google Sheets.

---

## 🚀 Funcionalidades

1. **Leitura de Prints e Faturas (Multimodal Vision):**
   - Você manda uma foto ou print da fatura, cupom fiscal, notificação de cartão ou comprovante Pix.
   - O agente analisa a imagem usando o **Gemini 1.5 Flash**, extrai os campos e classifica a despesa.
   - Insere automaticamente na aba correta (**`Pessoa Física`** ou **`PJ`**), replicando as fórmulas de distribuição mensal das colunas `K` a `Y`.

2. **Alerta Imediato de Orçamento por Categoria:**
   - O agente monitora os tetos de gastos mensais por categoria (ex: Mercado, Alimentação, Transporte, Beleza, etc.).
   - Sempre que um novo gasto é lançado, ele calcula o total acumulado no mês.
   - Se ultrapassar 100% (ou bater 80%), envia um alerta imediato no WhatsApp recomendando segurar os gastos.

3. **Lembretes Diários de Contas a Pagar (Data Limite):**
   - Agendamento diário (cron às 09:00) que varre as contas com status `Previsto` próximas do vencimento (hoje até 3 dias).
   - Envia um resumo no WhatsApp das contas que vencem hoje ou amanhã.
   - Você pode responder *"Paguei [nome da conta]"* e o agente atualiza o status para `Pago` na planilha.

---

## 📊 Estrutura da Sua Planilha

O agente foi desenhado especificamente para o layout da sua planilha:
- **Aba `Pessoa Física`:**
  - `Coluna A`: Data inicial
  - `Coluna B`: Descrição
  - `Coluna C`: Tipo (`Fixo`, `Parcelado`, `Variável`)
  - `Coluna D`: Categoria (Mercado, Alimentação, Transporte, Saúde, Pets / Amora, Assinaturas, Helo Saude, etc.)
  - `Coluna E`: Cartão / meio (`Nubank PF`, `Nubank PJ`, `Débito`, `Boleto`)
  - `Coluna F`: Valor mensal (R$)
  - `Coluna G`: Nº parcelas (se parcelado)
  - `Coluna H`: Data final (fixo)
  - `Coluna I`: Status (`Previsto`, `Pago`)
  - `Coluna J`: Observações
  - `Colunas K a Y`: Fórmulas automáticas de distribuição dos 15 meses (Out/26 a Dez/27)
- **Aba `PJ`:**
  - Despesas corporativas (Impostos PJ, Contabilidade, Capital Giro, etc.)
- **Aba `Overview`:**
  - Resumo de saldos e comparativo anual por categoria.

---

## 🛠️ Passo a Passo para Configuração

### 1. Obter a Chave do Google Gemini AI
1. Acesse o [Google AI Studio](https://aistudio.google.com/).
2. Clique em **Get API Key** e copie sua chave.
3. Coloque a chave no arquivo `.env` no campo `GEMINI_API_KEY`.

### 2. Acesso à Planilha via Google Sheets API
1. Acesse o [Google Cloud Console](https://console.cloud.google.com/).
2. Crie um projeto e ative a **Google Sheets API** e a **Google Drive API**.
3. Em **Credenciais**, crie uma **Conta de Serviço (Service Account)**.
4. Gere uma chave JSON e baixe-a como `credentials.json` dentro da pasta do projeto.
5. Abra a sua planilha no Google Sheets e compartilhe-a com o e-mail da conta de serviço (com permissão de **Editor**).

### 3. Conectar ao WhatsApp (Evolution API ou Z-API)
Para conversar no WhatsApp com seu próprio número pessoal sem burocracias corporativas da Meta, a melhor opção é a **Evolution API** (código aberto e gratuita):
- Pode ser instalada via Docker localmente ou em uma VPS barata (ex: Hetzner, Render, Railway, DigitalOcean):
  ```bash
  docker run -d --name evolution-api -p 8080:8080 \
    -e AUTHENTICATION_API_KEY=sua_chave_secreta \
    atendai/evolution-api:v2.1.2
  ```
- Escaneie o QR Code no seu WhatsApp (Aparelhos Conectados).
- Configure o Webhook na Evolution API apontando para `http://seu-servidor:8000/webhook`.

### 4. Executar o Agente

```bash
# 1. Crie o ambiente virtual
python3 -m venv venv
source venv/bin/activate

# 2. Instale as dependências
pip install -r requirements.txt

# 3. Configure as variáveis
cp .env.example .env
# Edite o .env com suas chaves

# 4. Inicie o servidor
python main.py
```

---

## 🔄 Alternativa Visual: n8n (No-Code / Low-Code)

Se você preferir não programar ou manter servidores Python, o mesmo fluxo pode ser criado no **n8n**:
1. **Nó Webhook:** Recebe a mensagem e a imagem do WhatsApp (Evolution API).
2. **Nó HTTP Request (Gemini Vision):** Envia a imagem para o Gemini com o prompt multimodal.
3. **Nó Google Sheets:** Adiciona a linha na aba `Pessoa Física`.
4. **Nó IF (Alerta de Orçamento):** Se o total gasto na categoria > limite, envia mensagem de alerta.
5. **Nó Cron (Schedule):** Roda todo dia às 09:00, busca despesas com status `Previsto` e envia o lembrete de vencimento.
