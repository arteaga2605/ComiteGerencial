# utils/ml_weights.py
import pandas as pd
from data.database import Database

class MLWeightAdjuster:
    def __init__(self):
        self.db = Database()
    
    def get_adjusted_weights(self, base_weights):
        """
        Ajusta los pesos de los analistas según su rendimiento histórico (aciertos).
        Usa una regla simple: peso = base_weight * (accuracy / 50)  (normalizado)
        """
        tickets = self.db.get_all_tickets()
        if tickets.empty:
            return base_weights
        
        accuracy = {}
        for analyst in base_weights.keys():
            df = tickets[tickets['analyst_name'] == analyst]
            if len(df) > 0:
                wins = len(df[df['result'] == 'win'])
                acc = wins / len(df) * 100
                accuracy[analyst] = acc
            else:
                accuracy[analyst] = 50  # neutral
        
        # Calcular nuevo peso
        adjusted = {}
        for analyst, w in base_weights.items():
            acc_factor = accuracy[analyst] / 50.0  # 1 si acierta 50%
            adjusted[analyst] = w * acc_factor
        
        # Normalizar para que sume 1
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: v/total for k, v in adjusted.items()}
        else:
            adjusted = base_weights
        
        return adjusted