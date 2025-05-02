from flask import Flask, request, jsonify, send_from_directory
from modelos import ProcesadorDTE
import os
import logging
from datetime import datetime

# Configuración básica de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('api.log')
    ]
)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'output'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB limit

# Asegurar que las carpetas existen
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

procesador = ProcesadorDTE()

@app.route('/api/process-xml', methods=['POST'])
def process_xml():
    try:
        app.logger.info("Iniciando procesamiento de archivo XML")
        
        if 'file' not in request.files:
            app.logger.error("No se proporcionó archivo en la solicitud")
            return jsonify({'success': False, 'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            app.logger.error("Nombre de archivo vacío")
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        if not (file and file.filename.lower().endswith('.xml')):
            app.logger.error("Formato de archivo no válido")
            return jsonify({'success': False, 'error': 'Invalid file format. Only XML files are allowed'}), 400

        # Guardar archivo temporalmente
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{file.filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        try:
            file.save(filepath)
            app.logger.info(f"Archivo guardado temporalmente en: {filepath}")
            
            # Procesar el archivo XML
            resultados = procesador.procesar_xml(filepath)
            app.logger.info("Archivo XML procesado correctamente")
            
            # Generar archivo de salida
            output_filename = 'autorizaciones.xml'
            output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
            procesador.generar_xml_salida(resultados, output_path)
            app.logger.info(f"Archivo de salida generado en: {output_path}")
            
            return jsonify({
                'success': True,
                'message': 'Archivo procesado correctamente',
                'resultados': resultados,
                'download_url': f'/api/download/{output_filename}',
                'details': {
                    'total_facturas': sum(f['facturas'] for f in resultados['fechas'].values()),
                    'facturas_correctas': resultados['correctas'],
                    'errores_totales': sum(resultados['errores'].values())
                }
            })
            
        except Exception as processing_error:
            app.logger.error(f"Error al procesar el archivo: {str(processing_error)}", exc_info=True)
            return jsonify({
                'success': False,
                'error': f"Error al procesar el archivo: {str(processing_error)}"
            }), 500
            
        finally:
            # Eliminar archivo temporal
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
                    app.logger.info(f"Archivo temporal {filepath} eliminado")
            except Exception as cleanup_error:
                app.logger.error(f"Error al eliminar archivo temporal: {str(cleanup_error)}")
                
    except Exception as general_error:
        app.logger.error(f"Error general en el endpoint: {str(general_error)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f"Error interno del servidor: {str(general_error)}"
        }), 500

@app.route('/api/download/<filename>', methods=['GET'])
def download_file(filename):
    try:
        app.logger.info(f"Solicitud de descarga para: {filename}")
        return send_from_directory(
            app.config['OUTPUT_FOLDER'],
            filename,
            as_attachment=True,
            mimetype='application/xml'
        )
    except Exception as e:
        app.logger.error(f"Error al descargar archivo: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 404

@app.route('/api/reset', methods=['POST'])
def reset():
    try:
        app.logger.info("Recibida solicitud de reset")
        procesador.__init__()
        
        # Limpiar carpeta de salida
        for filename in os.listdir(app.config['OUTPUT_FOLDER']):
            file_path = os.path.join(app.config['OUTPUT_FOLDER'], filename)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
                    app.logger.info(f"Archivo eliminado: {file_path}")
            except Exception as e:
                app.logger.error(f"Error al eliminar {file_path}: {str(e)}")
        
        return jsonify({
            'success': True,
            'message': 'Sistema reiniciado correctamente',
            'details': {
                'archivos_eliminados': len(os.listdir(app.config['OUTPUT_FOLDER']))
            }
        })
    except Exception as e:
        app.logger.error(f"Error en reset: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.logger.info("Iniciando servidor Flask")
    app.run(host='0.0.0.0', port=5000, debug=True)