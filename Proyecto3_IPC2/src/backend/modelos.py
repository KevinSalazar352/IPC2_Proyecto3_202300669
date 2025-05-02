import xml.etree.ElementTree as ET
from datetime import datetime
import re
import logging
from xml.dom import minidom

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
            self.fecha = self._parse_fecha(tiempo)
        except Exception as e:
            logger.error(f"Error al parsear fecha: {str(e)}")
            raise ValueError(f"Formato de fecha inválido: {str(e)}")
    
    def _parse_fecha(self, tiempo_str):
        if not tiempo_str:
            raise ValueError("Cadena de tiempo vacía")
        
        # Extraer fecha del formato "Guatemala, 20/03/2024 09:30 hrs."
        date_part = tiempo_str.split(',')[1].strip().split()[0] if ',' in tiempo_str else tiempo_str.split()[0]
        
        try:
            return datetime.strptime(date_part, '%d/%m/%Y').date()
        except ValueError:
            # Intentar otros formatos si es necesario
            raise ValueError(f"No se pudo parsear la fecha de: {tiempo_str}")

class ProcesadorDTE:
    def __init__(self):
        self.autorizaciones = []
        self.referencias = set()
        self.correlativos = {}
        self.logger = logging.getLogger(__name__)
    
    def procesar_xml(self, filepath):
        self.logger.info(f"Iniciando procesamiento de: {filepath}")
        
        try:
            tree = ET.parse(filepath)
            root = tree.getroot()
        except ET.ParseError as e:
            self.logger.error(f"Error al parsear XML: {str(e)}")
            raise ValueError(f"El archivo XML no es válido: {str(e)}")
        
        resultados = {
            'fechas': {},
            'errores': {
                'nit_emisor': 0,
                'nit_receptor': 0,
                'iva': 0,
                'total': 0,
                'referencia_duplicada': 0
            },
            'correctas': 0
        }
        
        for dte_element in root.findall('DTE'):
            try:
                dte = self._parse_dte(dte_element)
                fecha_str = dte.fecha.strftime('%d/%m/%Y')
                
                if fecha_str not in resultados['fechas']:
                    resultados['fechas'][fecha_str] = {
                        'facturas': 0,
                        'correctas': 0,
                        'emisores': set(),
                        'receptores': set()
                    }
                
                resultados['fechas'][fecha_str]['facturas'] += 1
                
                errores = self._validar_dte(dte)
                
                if not errores:
                    resultados['correctas'] += 1
                    resultados['fechas'][fecha_str]['correctas'] += 1
                    resultados['fechas'][fecha_str]['emisores'].add(dte.nit_emisor)
                    resultados['fechas'][fecha_str]['receptores'].add(dte.nit_receptor)
                    
                    # Generar código de autorización
                    codigo = self._generar_codigo_autorizacion(dte.fecha)
                    self.autorizaciones.append({
                        'fecha': fecha_str,
                        'nit_emisor': dte.nit_emisor,
                        'referencia': dte.referencia,
                        'codigo': codigo
                    })
                    self.logger.info(f"DTE aprobado: {dte.referencia} - Código: {codigo}")
                else:
                    for error in errores:
                        resultados['errores'][error] += 1
                    self.logger.warning(f"DTE con errores: {dte.referencia} - Errores: {', '.join(errores)}")
                        
            except Exception as e:
                self.logger.error(f"Error procesando DTE: {str(e)}", exc_info=True)
                continue
        
        self.logger.info(f"Procesamiento completado. Correctas: {resultados['correctas']}, Errores: {sum(resultados['errores'].values())}")
        return resultados
    
    def _parse_dte(self, dte_element):
        try:
            tiempo = dte_element.find('TIEMPO').text if dte_element.find('TIEMPO') is not None else None
            referencia = dte_element.find('REFERENCIA').text if dte_element.find('REFERENCIA') is not None else None
            nit_emisor = dte_element.find('NIT_EMISOR').text if dte_element.find('NIT_EMISOR') is not None else None
            nit_receptor = dte_element.find('NIT_RECEPTOR').text if dte_element.find('NIT_RECEPTOR') is not None else None
            valor = dte_element.find('VALOR').text if dte_element.find('VALOR') is not None else None
            iva = dte_element.find('IVA').text if dte_element.find('IVA') is not None else None
            total = dte_element.find('TOTAL').text if dte_element.find('TOTAL') is not None else None
            
            return DTE(tiempo, referencia, nit_emisor, nit_receptor, valor, iva, total)
        except Exception as e:
            self.logger.error(f"Error al parsear elemento DTE: {str(e)}")
            raise ValueError(f"Error en estructura DTE: {str(e)}")
    
    def _validar_dte(self, dte):
        errores = []
        
        # Validar NIT emisor
        if not self._validar_nit(dte.nit_emisor):
            errores.append('nit_emisor')
        
        # Validar NIT receptor
        if not self._validar_nit(dte.nit_receptor):
            errores.append('nit_receptor')
        
        # Validar IVA (12% del valor)
        iva_calculado = round(dte.valor * 0.12, 2)
        if abs(iva_calculado - dte.iva) > 0.01:  # Tolerancia para floats
            errores.append('iva')
        
        # Validar TOTAL (valor + IVA)
        total_calculado = dte.valor + dte.iva
        if abs(total_calculado - dte.total) > 0.01:  # Tolerancia para floats
            errores.append('total')
        
        # Validar referencia única
        if dte.referencia in self.referencias:
            errores.append('referencia_duplicada')
        else:
            self.referencias.add(dte.referencia)
        
        return errores
    
    def _validar_nit(self, nit):
        if not nit or len(nit) < 1:
            return False
        
        # El último carácter es el verificador
        verificador = nit[-1].upper()
        digitos = nit[:-1]
        
        # Todos los caracteres excepto el último deben ser dígitos
        if not digitos.isdigit():
            return False
        
        # Calcular dígito verificador
        suma = 0
        for i, d in enumerate(reversed(digitos), start=2):
            suma += int(d) * i
        
        mod = suma % 11
        calc_verificador = 11 - mod
        
        # Casos especiales
        if calc_verificador == 11:
            calc_verificador = 0
        elif calc_verificador == 10:
            calc_verificador = 'K'
        
        return str(calc_verificador) == verificador
    
    def _generar_codigo_autorizacion(self, fecha):
        fecha_str = fecha.strftime('%Y%m%d')
        
        if fecha_str not in self.correlativos:
            self.correlativos[fecha_str] = 1
        else:
            self.correlativos[fecha_str] += 1
        
        correlativo = str(self.correlativos[fecha_str]).zfill(8)
        return f"{fecha_str}{correlativo}"
    
    def generar_xml_salida(self, resultados, output_path):
        try:
            self.logger.info(f"Generando archivo de salida: {output_path}")
            
            root = ET.Element('LISTAAUTORIZACIONES')
            
            for fecha_str, datos_fecha in resultados['fechas'].items():
                autorizacion = ET.SubElement(root, 'AUTORIZACION')
                
                ET.SubElement(autorizacion, 'FECHA').text = fecha_str
                ET.SubElement(autorizacion, 'FACTURAS_RECIBIDAS').text = str(datos_fecha['facturas'])
                
                errores = ET.SubElement(autorizacion, 'ERRORES')
                ET.SubElement(errores, 'NIT_EMISOR').text = str(resultados['errores']['nit_emisor'])
                ET.SubElement(errores, 'NIT_RECEPTOR').text = str(resultados['errores']['nit_receptor'])
                ET.SubElement(errores, 'IVA').text = str(resultados['errores']['iva'])
                ET.SubElement(errores, 'TOTAL').text = str(resultados['errores']['total'])
                ET.SubElement(errores, 'REFERENCIA_DUPLICADA').text = str(resultados['errores']['referencia_duplicada'])
                
                ET.SubElement(autorizacion, 'FACTURAS_CORRECTAS').text = str(datos_fecha['correctas'])
                ET.SubElement(autorizacion, 'CANTIDAD_EMISORES').text = str(len(datos_fecha['emisores']))
                ET.SubElement(autorizacion, 'CANTIDAD_RECEPTORES').text = str(len(datos_fecha['receptores']))
                
                listado = ET.SubElement(autorizacion, 'LISTADO_AUTORIZACIONES')
                for auth in [a for a in self.autorizaciones if a['fecha'] == fecha_str]:
                    aprobacion = ET.SubElement(listado, 'APROBACION')
                    ET.SubElement(aprobacion, 'NIT_EMISOR', ref=auth['referencia']).text = auth['nit_emisor']
                    ET.SubElement(aprobacion, 'CODIGO_APROBACION').text = auth['codigo']
                
                ET.SubElement(listado, 'TOTAL_APROBACIONES').text = str(datos_fecha['correctas'])
            
            # Formatear el XML con indentación
            xml_str = ET.tostring(root, encoding='utf-8')
            xml_pretty = minidom.parseString(xml_str).toprettyxml(indent="  ", encoding='utf-8')
            
            with open(output_path, 'wb') as f:
                f.write(xml_pretty)
            
            self.logger.info("Archivo de salida generado exitosamente")
            
        except Exception as e:
            self.logger.error(f"Error al generar XML de salida: {str(e)}", exc_info=True)
            raise ValueError(f"Error al generar archivo de salida: {str(e)}")