# utils/ticket_manager.py (modificado para incluir símbolo)
from data.database import Database
from datetime import datetime

class TicketManager:
    def __init__(self):
        self.db = Database()
    
    def create_ticket(self, analyst_name, operation, entry_price, exit_price, result, profit_loss, comment='', symbol='BTCUSDT'):
        self.db.save_ticket(analyst_name, operation, entry_price, exit_price, result, profit_loss, comment, symbol)
        print(f"Ticket creado para {analyst_name} - {operation} - Resultado: {result} - Símbolo: {symbol}")
    
    def interactive_ticket(self):
        print("=== Creación de Ticket (Acierto/Fallo) ===")
        analyst = input("Nombre del analista (Analyst_1H, Analyst_4H, Analyst_1D, Analyst_1M, Leader_Committee): ")
        symbol = input("Símbolo (ej. BTCUSDT, ETHUSDT): ").upper() or 'BTCUSDT'
        operation = input("Operación (BUY/SELL): ").upper()
        entry = float(input("Precio de entrada: "))
        exit_price = float(input("Precio de salida: "))
        result = input("Resultado (win/loss): ").lower()
        if result not in ['win', 'loss']:
            print("Resultado inválido. Use 'win' o 'loss'.")
            return
        if result == 'win':
            if operation == 'BUY':
                pnl = exit_price - entry
            else:
                pnl = entry - exit_price
        else:
            if operation == 'BUY':
                pnl = entry - exit_price
            else:
                pnl = exit_price - entry
        comment = input("Comentario (opcional): ")
        self.create_ticket(analyst, operation, entry, exit_price, result, round(pnl, 2), comment, symbol)