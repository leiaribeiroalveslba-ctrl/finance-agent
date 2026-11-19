# budget_service.py
from typing import Dict, Optional, Tuple

# Orçamentos previstos padrão por categoria (limite mensal em R$)
# Você pode ajustar esses valores ou carregá-los de uma aba da planilha
DEFAULT_BUDGETS_PF: Dict[str, float] = {
    "Mercado": 800.0,
    "Alimentação": 600.0,
    "Transporte": 350.0,
    "Uber": 250.0,
    "Pets / Amora": 300.0,
    "Beleza": 350.0,
    "Compras pessoais": 400.0,
    "Vestuario": 300.0,
    "Lazer": 300.0,
    "Assinaturas": 250.0,
    "Saúde": 1500.0,
    "Moradia": 3500.0,
    "Educação": 1000.0
}

class BudgetService:
    def __init__(self, budgets_pf: Optional[Dict[str, float]] = None):
        self.budgets_pf = budgets_pf or DEFAULT_BUDGETS_PF

    def set_budget(self, categoria: str, valor: float):
        self.budgets_pf[categoria] = valor

    def check_budget_alert(self, categoria: str, total_gasto_mes: float) -> Tuple[bool, Optional[str]]:
        """
        Verifica se a categoria possui teto de orçamento e se foi estourado ou está em alerta (>80%).
        Retorna (estourou, mensagem_alerta).
        """
        limite = self.budgets_pf.get(categoria)
        if not limite or limite <= 0:
            return False, None

        percentual = (total_gasto_mes / limite) * 100

        if total_gasto_mes > limite:
            excesso = total_gasto_mes - limite
            msg = (
                f"🚨 *ALERTA DE ORÇAMENTO ESTOURADO!*\n\n"
                f"• Categoria: *{categoria}*\n"
                f"• Orçamento previsto: *R$ {limite:,.2f}*\n"
                f"• Gasto acumulado no mês: *R$ {total_gasto_mes:,.2f}*\n"
                f"• Excesso: *R$ {excesso:,.2f}* ({percentual:.1f}% do teto previsto)\n\n"
                f"Recomendo segurar os gastos desta categoria até o próximo mês!"
            )
            return True, msg
        elif percentual >= 80.0:
            msg = (
                f"⚠️ *Aviso de Orçamento Quase no Limite*\n\n"
                f"• Categoria: *{categoria}*\n"
                f"• Orçamento previsto: *R$ {limite:,.2f}*\n"
                f"• Gasto acumulado no mês: *R$ {total_gasto_mes:,.2f}* ({percentual:.1f}%)\n"
                f"• Restam apenas: *R$ {(limite - total_gasto_mes):,.2f}*"
            )
            return False, msg

        return False, None
