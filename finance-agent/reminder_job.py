# reminder_job.py
from datetime import datetime
from typing import List, Dict, Any, Callable
from sheets_service import SheetsService

class ReminderJob:
    def __init__(self, sheets_service: SheetsService, send_whatsapp_fn: Callable[[str], bool]):
        self.sheets = sheets_service
        self.send_whatsapp = send_whatsapp_fn

    def check_and_send_reminders(self, dias_antecedencia: int = 3):
        """
        Executa a verificação de contas a vencer e dispara lembretes no WhatsApp.
        """
        pendentes = self.sheets.get_pagamentos_pendentes(dias_antecedencia=dias_antecedencia)
        if not pendentes:
            return

        linhas_msg = ["🔔 *LEMBRETE DE PAGAMENTOS PENDENTES*\n"]
        linhas_msg.append("Identifiquei contas próximas da data limite de vencimento:\n")

        for i, item in enumerate(pendentes, 1):
            dias = item["dias_restantes"]
            if dias == 0:
                prazo_txt = "🚨 *VENCE HOJE!*"
            elif dias == 1:
                prazo_txt = "⚠️ *Vence amanhã!*"
            else:
                prazo_txt = f"Vence em {dias} dias"

            linhas_msg.append(
                f"{i}. *{item['descricao']}* ({item['categoria']})\n"
                f"   • Valor: R$ {float(item['valor']):,.2f}\n"
                f"   • Vencimento: {item['data_vencimento']} ({prazo_txt})\n"
                f"   • Aba: {item['aba']} (Linha {item['linha']})\n"
            )

        linhas_msg.append("💡 *Dica:* Quando realizar o pagamento, me avise dizendo:\n*'Paguei [nome da conta]'* que atualizo o status para 'Pago' na planilha!")

        mensagem_final = "\n".join(linhas_msg)
        self.send_whatsapp(mensagem_final)
