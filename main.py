# main.py
import os
import json
import base64
import requests
from datetime import datetime
from fastapi import FastAPI, Request, BackgroundTasks
import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler

from prompt_vision import EXTRACTION_SYSTEM_PROMPT
from sheets_service import SheetsService
from budget_service import BudgetService
from reminder_job import ReminderJob

# Variáveis de ambiente
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "1DGdynvDY-wSxyyfhbIeoLoKN1Ls2Ckrq")
CREDENTIALS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json")
WHATSAPP_API_URL = os.getenv("WHATSAPP_API_URL", "")
WHATSAPP_API_KEY = os.getenv("WHATSAPP_API_KEY", "")
USER_PHONE_NUMBER = os.getenv("USER_PHONE_NUMBER", "")

app = FastAPI(title="Agente Financeiro WhatsApp")

# Serviços
sheets_service = SheetsService(CREDENTIALS_PATH, SPREADSHEET_ID)
budget_service = BudgetService()

def send_whatsapp_message(text: str, to: str = USER_PHONE_NUMBER) -> bool:
    """
    Envia mensagem via Z-API ou Evolution API.
    Detecta automaticamente o formato pelo link informado no WHATSAPP_API_URL.
    """
    if not WHATSAPP_API_URL or not to:
        print(f"[MOCK WHATSAPP SEND]: Para={to} | Mensagem=\n{text}")
        return True

    try:
        # Se for Z-API (ex: https://api.z-api.io/instances/.../token/...)
        if "z-api.io" in WHATSAPP_API_URL:
            url = WHATSAPP_API_URL.rstrip("/")
            if not url.endswith("/send-text"):
                url = f"{url}/send-text"
            
            headers = {
                "Client-Token": WHATSAPP_API_KEY,
                "Content-Type": "application/json"
            }
            payload = {
                "phone": to,
                "message": text
            }
            resp = requests.post(url, json=payload, headers=headers, timeout=15)
            return resp.status_code in [200, 201]

        # Se for Evolution API
        else:
            url = f"{WHATSAPP_API_URL.rstrip('/')}/message/sendText/default"
            headers = {
                "apikey": WHATSAPP_API_KEY,
                "Content-Type": "application/json"
            }
            payload = {
                "number": to,
                "text": text
            }
            resp = requests.post(url, json=payload, headers=headers, timeout=15)
            return resp.status_code in [200, 201]

    except Exception as e:
        print(f"Erro ao enviar WhatsApp: {e}")
        return False

# Inicializa agendador de lembretes diários
reminder_job = ReminderJob(sheets_service, send_whatsapp_message)
scheduler = BackgroundScheduler()

@app.on_event("startup")
def startup_event():
    # Agenda para rodar todo dia às 09:00 da manhã
    scheduler.add_job(reminder_job.check_and_send_reminders, "cron", hour=9, minute=0)
    scheduler.start()
    print("Agente Financeiro iniciado com sucesso. Agendador de lembretes ativo.")

@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()

def process_image_with_gemini(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    """
    Envia a imagem para o modelo Gemini 1.5 Flash com o prompt de extração estruturada.
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    b64_image = base64.b64encode(image_bytes).decode("utf-8")
    
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": EXTRACTION_SYSTEM_PROMPT},
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": b64_image
                        }
                    }
                ]
            }
        ],
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": 0.1
        }
    }
    
    resp = requests.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    result_json = resp.json()
    
    raw_text = result_json["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(raw_text)

def handle_incoming_media(image_bytes: bytes, mime_type: str, sender_phone: str):
    """
    Processa imagem recebida (print de fatura, cupom fiscal ou comprovante).
    """
    send_whatsapp_message("🔍 Analisando seu comprovante/fatura...", sender_phone)
    
    try:
        dados_extraidos = process_image_with_gemini(image_bytes, mime_type)
        itens = dados_extraidos.get("itens", [])
        
        if not itens:
            send_whatsapp_message("⚠️ Não consegui identificar nenhuma despesa clara na imagem enviada. Pode tentar mandar outro print mais nítido?", sender_phone)
            return

        respostas = ["✅ *Despesa(s) Registrada(s) na Planilha:*\n"]
        now = datetime.now()

        for item in itens:
            aba = item.get("aba_destino", "Pessoa Física")
            
            # 1. Inserir na Planilha Google
            if aba == "PJ":
                linha = sheets_service.append_despesa_pj(item)
            else:
                linha = sheets_service.append_despesa_pf(item)

            valor = float(item.get("valor_mensal", 0.0))
            categoria = item.get("categoria", "Outros")
            tipo = item.get("tipo", "Variável")
            desc = item.get("descricao", "Sem descrição")

            respostas.append(
                f"• *{desc}*\n"
                f"  - Valor: R$ {valor:,.2f} ({tipo})\n"
                f"  - Categoria: {categoria}\n"
                f"  - Aba: {aba} (Linha {linha})\n"
            )

            # 2. Verificar Orçamento da Categoria (se for Pessoa Física)
            if aba == "Pessoa Física":
                total_mes = sheets_service.get_gastos_mes_categoria(categoria, now.year, now.month)
                estourou, msg_alerta = budget_service.check_budget_alert(categoria, total_mes)
                if msg_alerta:
                    respostas.append(f"\n{msg_alerta}\n")

        mensagem_final = "\n".join(respostas)
        send_whatsapp_message(mensagem_final, sender_phone)

    except Exception as e:
        print(f"Erro ao processar mídia: {e}")
        send_whatsapp_message(f"❌ Ocorreu um erro ao processar o print: {str(e)}", sender_phone)

def handle_incoming_text(text: str, sender_phone: str):
    """
    Processa mensagens de texto simples (comandos, consultas ou marcação de pagamento).
    """
    clean_text = text.strip().lower()

    # Comando para marcar pagamento
    if "paguei" in clean_text or "pago" in clean_text:
        pendentes = sheets_service.get_pagamentos_pendentes(dias_antecedencia=30)
        encontrado = None
        for p in pendentes:
            if p["descricao"].lower() in clean_text:
                encontrado = p
                break
        
        if encontrado:
            sheets_service.marcar_como_pago(encontrado["aba"], encontrado["linha"])
            send_whatsapp_message(f"✅ Boa! O pagamento de *{encontrado['descricao']}* (R$ {encontrado['valor']}) foi marcado como *Pago* na planilha!", sender_phone)
        else:
            send_whatsapp_message("Marquei! Se quiser verificar o status de todas as contas, basta pedir 'lembretes'.", sender_phone)
        return

    # Comando de lembretes manuais
    if "lembrete" in clean_text or "contas a vencer" in clean_text or "o que tenho que pagar" in clean_text:
        reminder_job.check_and_send_reminders(dias_antecedencia=7)
        return

    # Ajuda padrão
    msg_ajuda = (
        "👋 Olá! Sou seu Agente Pessoal Financeiro.\n\n"
        "Você pode:\n"
        "📸 *Enviar prints de faturas, recibos ou boletos*: Eu leio os valores e preencho sua planilha automaticamente.\n"
        "🔔 *Lembretes*: Eu te aviso todos os dias às 09:00 sobre contas a vencer.\n"
        "🚨 *Orçamento*: Eu te alerto no mesmo instante caso estoure o teto de alguma categoria.\n"
        "✅ Digite *'paguei [nome da conta]'* para atualizar o status para Pago."
    )
    send_whatsapp_message(msg_ajuda, sender_phone)

@app.get("/")
def health_check():
    return {"status": "online", "message": "Agente Financeiro funcionando perfeitamente!"}

@app.post("/webhook")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Endpoint compatível com Z-API e Evolution API.
    """
    data = await request.json()
    
    try:
        # 1. Tratamento para Z-API
        if "phone" in data:
            sender = str(data.get("phone", ""))
            
            # Se a Z-API enviou imagem
            image_url = data.get("image", {}).get("imageUrl") or data.get("imageUrl")
            if image_url:
                resp = requests.get(image_url, timeout=20)
                if resp.status_code == 200:
                    background_tasks.add_task(handle_incoming_media, resp.content, "image/jpeg", sender)
                    return {"status": "processing_zapi_image"}

            # Se a Z-API enviou texto
            text = data.get("text", {}).get("message") or data.get("message") or data.get("body")
            if text:
                background_tasks.add_task(handle_incoming_text, str(text), sender)
                return {"status": "processing_zapi_text"}

        # 2. Tratamento para Evolution API
        message_data = data.get("data", {})
        if message_data:
            sender = message_data.get("key", {}).get("remoteJid", "").split("@")[0] or USER_PHONE_NUMBER
            message_content = message_data.get("message", {})

            if "imageMessage" in message_content:
                base64_img = message_data.get("base64")
                if base64_img:
                    image_bytes = base64.b64decode(base64_img)
                    background_tasks.add_task(handle_incoming_media, image_bytes, "image/jpeg", sender)
                return {"status": "processing_evolution_image"}

            text = message_content.get("conversation") or message_content.get("extendedTextMessage", {}).get("text")
            if text:
                background_tasks.add_task(handle_incoming_text, str(text), sender)
                return {"status": "processing_evolution_text"}

    except Exception as e:
        print(f"Erro no webhook: {e}")

    return {"status": "ignored"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
