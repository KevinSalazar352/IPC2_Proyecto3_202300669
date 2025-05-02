from datetime import datetime
import re
import logging

logger = logging.getLogger(__name__)

class DTE:
    def __init__(self, tiempo, referencia, nit_emisor, nit_receptor, valor, iva, total):
        self.tiempo = tiempo.strip() if tiempo else None
        self.referencia = referencia.strip() if referencia else None
        self.nit_emisor = nit_emisor.strip() if nit_emisor else None
        self.nit_receptor = nit_receptor.strip() if nit_receptor else None
        
        try:
            self.valor = float(valor) if valor else 0.0
            self.iva = float(iva) if iva else 0.0
            self.total = float(total) if total else 0.0
        except (ValueError, TypeError) as e:
            logger.error(f"Error al convertir valores numéricos: {str(e)}")
            raise ValueError(f"Valores numéricos inválidos: {str(e)}")
        
        try:
            self.fecha = self._parse_fecha(self.tiempo)
        except Exception as e:
            logger.error(f"Error al parsear fecha: {str(e)}")
            raise ValueError(f"Formato de fecha inválido: {str(e)}")
    
    def _parse_fecha(self, tiempo_str):
        if not tiempo_str:
            raise ValueError("Cadena de tiempo vacía")
        
        try:
            # Extraer la parte de la fecha (formato: "Guatemala, 20/03/2024 09:30 hrs.")
            date_part = tiempo_str.split(',')[1].strip().split()[0] if ',' in tiempo_str else tiempo_str.split()[0]
            return datetime.strptime(date_part, '%d/%m/%Y').date()
        except ValueError as e:
            # Intentar otros formatos comunes si falla el primer intento
            try:
                # Formato alternativo sin lugar: "20/03/2024 09:30 hrs."
                date_part = tiempo_str.split()[0]
                return datetime.strptime(date_part, '%d/%m/%Y').date()
            except:
                raise ValueError(f"No se pudo parsear la fecha de: {tiempo_str}. Error: {str(e)}")