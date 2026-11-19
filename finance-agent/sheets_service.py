# sheets_service.py
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

class SheetsService:
    def __init__(self, credentials_path: str, spreadsheet_id: str):
        self.credentials_path = credentials_path
        self.spreadsheet_id = spreadsheet_id
        self.client = None
        self.doc = None
        self._init_client()

    def _init_client(self):
        if os.path.exists(self.credentials_path):
            creds = Credentials.from_service_account_file(self.credentials_path, scopes=SCOPES)
            self.client = gspread.authorize(creds)
            self.doc = self.client.open_by_key(self.spreadsheet_id)

    def append_despesa_pf(self, item: Dict[str, Any]) -> int:
        """
        Insere uma despesa na aba 'Pessoa Física'.
        Colunas A-J:
        A: Data (YYYY-MM-DD ou formato DD/MM/AAAA)
        B: Descrição
        C: Tipo (Fixo, Parcelado, Variável)
        D: Categoria
        E: Cartão / meio
        F: Valor mensal (R$)
        G: Nº parcelas
        H: Data final (fixo)
        I: Status (Previsto, Pago)
        J: Observações
        Colunas K-Y: Fórmulas mensais herdadas da linha anterior.
        """
        sheet = self.doc.worksheet("Pessoa Física")
        all_values = sheet.get_all_values()
        
        # Encontra a primeira linha vazia a partir da linha 14
        next_row = len(all_values) + 1
        for i in range(13, len(all_values)):
            row = all_values[i]
            # Se a descrição (coluna B) e valor (coluna F) estiverem vazios
            if not row[1] and not row[5]:
                next_row = i + 1
                break

        prev_row = next_row - 1 if next_row > 14 else 14

        # Formata data para DD/MM/AAAA se estiver em YYYY-MM-DD
        data_str = item.get("data", "")
        if "-" in data_str:
            try:
                dt = datetime.strptime(data_str, "%Y-%m-%d")
                data_str = dt.strftime("%d/%m/%Y")
            except Exception:
                pass

        row_data = [
            data_str,
            item.get("descricao", ""),
            item.get("tipo", "Variável"),
            item.get("categoria", "Outros"),
            item.get("cartao_meio", "Nubank PF"),
            float(item.get("valor_mensal", 0.0)),
            item.get("num_parcelas") if item.get("tipo") == "Parcelado" else "",
            item.get("data_final", ""),
            item.get("status", "Previsto"),
            item.get("observacoes", "")
        ]

        # Atualiza colunas A até J
        cell_range_aj = f"A{next_row}:J{next_row}"
        sheet.update(cell_range_aj, [row_data], value_input_option="USER_ENTERED")

        # Garante que as fórmulas das colunas K a Y sejam copiadas da linha anterior
        # Na sua planilha, as colunas K a Y contêm fórmulas dinâmicas que distribuem os valores por mês
        try:
            prev_formulas = sheet.get(f"K{prev_row}:Y{prev_row}", value_render_option="FORMULA")
            if prev_formulas and len(prev_formulas) > 0:
                new_formulas = []
                for f in prev_formulas[0]:
                    # Atualiza as referências de linha (ex: $A18 -> $A{next_row})
                    f_adjusted = f.replace(f"${prev_row}", f"${next_row}").replace(f"{prev_row}", f"{next_row}")
                    new_formulas.append(f_adjusted)
                sheet.update(f"K{next_row}:Y{next_row}", [new_formulas], value_input_option="USER_ENTERED")
        except Exception as e:
            print(f"Aviso ao replicar fórmulas K:Y: {e}")

        return next_row

    def append_despesa_pj(self, item: Dict[str, Any]) -> int:
        """
        Insere uma despesa na aba 'PJ'.
        Colunas:
        A: Data inicial
        B: Descrição
        C: Categoria
        D: Frequência (Mensal, Avulso)
        E: Valor (R$)
        F: Data final (opcional)
        G: Observação
        """
        sheet = self.doc.worksheet("PJ")
        all_values = sheet.get_all_values()
        
        next_row = len(all_values) + 1
        for i in range(13, len(all_values)):
            row = all_values[i]
            if not row[1] and not row[4]:
                next_row = i + 1
                break

        prev_row = next_row - 1 if next_row > 14 else 14

        data_str = item.get("data", "")
        if "-" in data_str:
            try:
                dt = datetime.strptime(data_str, "%Y-%m-%d")
                data_str = dt.strftime("%d/%m/%Y")
            except Exception:
                pass

        freq = "Mensal" if item.get("tipo") == "Fixo" else "Avulso"

        row_data = [
            data_str,
            item.get("descricao", ""),
            item.get("categoria", "Outros PJ"),
            freq,
            float(item.get("valor_mensal", 0.0)),
            item.get("data_final", ""),
            item.get("observacoes", "")
        ]

        sheet.update(f"A{next_row}:G{next_row}", [row_data], value_input_option="USER_ENTERED")

        # Fórmulas de meses H:V
        try:
            prev_formulas = sheet.get(f"H{prev_row}:V{prev_row}", value_render_option="FORMULA")
            if prev_formulas and len(prev_formulas) > 0:
                new_formulas = []
                for f in prev_formulas[0]:
                    f_adjusted = f.replace(f"${prev_row}", f"${next_row}").replace(f"{prev_row}", f"{next_row}")
                    new_formulas.append(f_adjusted)
                sheet.update(f"H{next_row}:V{next_row}", [new_formulas], value_input_option="USER_ENTERED")
        except Exception as e:
            print(f"Aviso ao replicar fórmulas H:V em PJ: {e}")

        return next_row

    def get_gastos_mes_categoria(self, categoria: str, ano: int, mes: int, aba: str = "Pessoa Física") -> float:
        """
        Calcula o total gasto na categoria especificada no mês/ano atual.
        """
        sheet = self.doc.worksheet(aba)
        all_values = sheet.get_all_values()

        # Mapeamento do mês para a coluna correspondente (K = Out/26, L = Nov/26, ...)
        # K13 = Out/26, L13 = Nov/26, M13 = Dez/26, N13 = Jan/27, O13 = Fev/27...
        header_row = all_values[12] if len(all_values) > 12 else []
        col_index = None

        meses_abrev = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
        target_label = f"{meses_abrev[mes - 1]}/{str(ano)[-2:]}"

        for idx, val in enumerate(header_row):
            if target_label.lower() in val.lower():
                col_index = idx
                break

        total = 0.0
        for row in all_values[13:]:
            if len(row) > 3 and row[3].strip().lower() == categoria.strip().lower():
                # Se encontrou a coluna do mês nas fórmulas
                if col_index is not None and len(row) > col_index:
                    val_str = row[col_index].replace("R$", "").replace(".", "").replace(",", ".").strip()
                    try:
                        total += float(val_str)
                    except ValueError:
                        pass
                else:
                    # Fallback somando valor mensal se a data coincidir
                    val_str = row[5].replace("R$", "").replace(".", "").replace(",", ".").strip() if len(row) > 5 else "0"
                    try:
                        total += float(val_str)
                    except ValueError:
                        pass

        return total

    def get_pagamentos_pendentes(self, dias_antecedencia: int = 3) -> List[Dict[str, Any]]:
        """
        Varre as abas 'Pessoa Física' e 'PJ' procurando lançamentos com Status 'Previsto'
        cuja data de pagamento esteja próxima (hoje até X dias).
        """
        pendentes = []
        today = datetime.now().date()

        for aba_name in ["Pessoa Física", "PJ"]:
            sheet = self.doc.worksheet(aba_name)
            rows = sheet.get_all_records()
            is_pj = (aba_name == "PJ")

            for idx, row in enumerate(rows, start=14):
                status = row.get("Status", "").strip() if not is_pj else "Previsto"
                if status.lower() == "previsto" or is_pj:
                    data_str = row.get("Data inicial", "")
                    if not data_str:
                        continue
                    
                    data_venc = None
                    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y"):
                        try:
                            data_venc = datetime.strptime(str(data_str), fmt).date()
                            break
                        except ValueError:
                            pass
                    
                    if data_venc:
                        dias_restantes = (data_venc - today).days
                        if 0 <= dias_restantes <= dias_antecedencia:
                            pendentes.append({
                                "aba": aba_name,
                                "linha": idx,
                                "descricao": row.get("Descrição", "Sem descrição"),
                                "categoria": row.get("Categoria", ""),
                                "valor": row.get("Valor mensal (R$)" if not is_pj else "Valor (R$)", 0),
                                "data_vencimento": data_venc.strftime("%d/%m/%Y"),
                                "dias_restantes": dias_restantes
                            })
        return pendentes

    def marcar_como_pago(self, aba: str, linha: int) -> bool:
        """
        Atualiza o status de um lançamento para 'Pago'.
        """
        try:
            sheet = self.doc.worksheet(aba)
            if aba == "Pessoa Física":
                sheet.update_cell(linha, 9, "Pago") # Coluna I = Status
            return True
        except Exception as e:
            print(f"Erro ao marcar como pago: {e}")
            return False
