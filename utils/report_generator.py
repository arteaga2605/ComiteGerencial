# utils/report_generator.py
import pandas as pd
import matplotlib.pyplot as plt
from data.database import Database
import os

class ReportGenerator:
    def __init__(self):
        self.db = Database()
    
    def calculate_accuracy(self, symbol=None):
        tickets = self.db.get_all_tickets(symbol=symbol)
        if tickets.empty:
            return {}
        
        accuracy = {}
        analysts = tickets['analyst_name'].unique()
        for analyst in analysts:
            df_analyst = tickets[tickets['analyst_name'] == analyst]
            total = len(df_analyst)
            wins = len(df_analyst[df_analyst['result'] == 'win'])
            acc = (wins / total) * 100 if total > 0 else 0
            accuracy[analyst] = {'total': total, 'wins': wins, 'accuracy': acc}
        return accuracy
    
    def generate_performance_chart(self, save_path='performance.png', symbol=None):
        accuracy = self.calculate_accuracy(symbol=symbol)
        if not accuracy:
            print(f"No hay datos de tickets para generar gráfico{f' del símbolo {symbol}' if symbol else ''}.")
            return
        
        analysts = list(accuracy.keys())
        acc_values = [accuracy[a]['accuracy'] for a in analysts]
        total_trades = [accuracy[a]['total'] for a in analysts]
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
        
        title_suffix = f" para {symbol}" if symbol else ""
        ax1.bar(analysts, acc_values, color=['green' if v>=50 else 'red' for v in acc_values])
        ax1.set_ylabel('Porcentaje de aciertos (%)')
        ax1.set_title(f'Precisión por Analista{title_suffix}')
        ax1.set_ylim(0, 100)
        for i, v in enumerate(acc_values):
            ax1.text(i, v + 1, f"{v:.1f}%", ha='center')
        
        ax2.bar(analysts, total_trades, color='skyblue')
        ax2.set_ylabel('Número de operaciones')
        ax2.set_title(f'Total de operaciones registradas{title_suffix}')
        for i, v in enumerate(total_trades):
            ax2.text(i, v + 0.5, str(v), ha='center')
        
        plt.tight_layout()
        filename = f"performance_{symbol}.png" if symbol else save_path
        plt.savefig(filename)
        plt.close()
        print(f"Gráfico guardado en {filename}")
    
    def generate_text_report(self, symbol=None):
        accuracy = self.calculate_accuracy(symbol=symbol)
        if not accuracy:
            return f"No hay suficientes tickets para generar reporte{f' de {symbol}' if symbol else ''}.\n"
        
        header = f"=== REPORTE DE RENDIMIENTO POR ANALISTA{f' - {symbol}' if symbol else ''} ===\n\n"
        lines = [header]
        for analyst, data in accuracy.items():
            lines.append(f"{analyst}:")
            lines.append(f"  Operaciones totales: {data['total']}")
            lines.append(f"  Aciertos: {data['wins']}")
            lines.append(f"  Porcentaje de acierto: {data['accuracy']:.2f}%\n")
        return '\n'.join(lines)
    
    def generate_full_report(self):
        """Genera reporte global y por cada símbolo disponible"""
        # Reporte global
        global_text = self.generate_text_report()
        print(global_text)
        self.generate_performance_chart(save_path='performance_global.png', symbol=None)
        
        # Obtener símbolos únicos de tickets
        tickets = self.db.get_all_tickets()
        if not tickets.empty and 'symbol' in tickets.columns:
            symbols = tickets['symbol'].unique()
            for sym in symbols:
                print(f"\n--- Reporte para {sym} ---")
                sym_text = self.generate_text_report(symbol=sym)
                print(sym_text)
                self.generate_performance_chart(save_path=f'performance_{sym}.png', symbol=sym)