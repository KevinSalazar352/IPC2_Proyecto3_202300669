import os
import logging
from django.shortcuts import render
from django.http import JsonResponse
from django.conf import settings
from django.core.files.storage import FileSystemStorage
import requests

logger = logging.getLogger(__name__)

def index(request):
    context = {}
    
    if request.method == 'POST' and request.FILES.get('xml_file'):
        try:
            uploaded_file = request.FILES['xml_file']
            fs = FileSystemStorage()
            filename = fs.save(uploaded_file.name, uploaded_file)
            filepath = fs.path(filename)
            
            logger.info(f"Archivo recibido: {filename}")
            
            try:
                with open(filepath, 'rb') as f:
                    files = {'file': f}
                    
                    logger.info("Enviando archivo a la API...")
                    
                    response = requests.post(
                        f"{settings.API_URL}/process-xml",
                        files=files,
                        timeout=settings.API_TIMEOUT
                    )
                    
                    logger.info(f"Respuesta de la API: {response.status_code}")
                    
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('success'):
                            context.update({
                                'success': data['message'],
                                'resultados': data['resultados'],
                                'download_url': data['download_url'],
                                'details': data.get('details', {})
                            })
                            logger.info("Procesamiento exitoso")
                        else:
                            context['error'] = data.get('error', 'Error desconocido en la API')
                            logger.error(f"Error en la API: {context['error']}")
                    else:
                        try:
                            error_data = response.json()
                            context['error'] = f"{response.status_code} - {error_data.get('error', 'Error desconocido')}"
                        except ValueError:
                            context['error'] = f"Error {response.status_code} en la API"
                        logger.error(f"Error HTTP {response.status_code}: {context['error']}")
                        
            except requests.exceptions.RequestException as e:
                logger.error(f"Error de conexión con la API: {str(e)}")
                context['error'] = f"Error al conectar con la API: {str(e)}"
                
            except Exception as e:
                logger.error(f"Error inesperado: {str(e)}", exc_info=True)
                context['error'] = f"Error inesperado: {str(e)}"
                
            finally:
                try:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                        logger.info(f"Archivo temporal {filename} eliminado")
                except Exception as e:
                    logger.error(f"Error al eliminar archivo temporal: {str(e)}")
        
        except Exception as e:
            logger.error(f"Error general al procesar archivo: {str(e)}", exc_info=True)
            context['error'] = f"Error al procesar el archivo: {str(e)}"
    
    return render(request, 'page/index.html', context)

def reset_system(request):
    if request.method == 'POST':
        try:
            logger.info("Solicitando reset del sistema")
            response = requests.post(
                f"{settings.API_URL}/reset",
                timeout=settings.API_TIMEOUT
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info("Reset exitoso")
                return JsonResponse(data)
            else:
                error_msg = f"Error {response.status_code} al resetear el sistema"
                logger.error(error_msg)
                return JsonResponse({'success': False, 'error': error_msg}, status=response.status_code)
                
        except requests.exceptions.RequestException as e:
            error_msg = f"Error de conexión al resetear: {str(e)}"
            logger.error(error_msg)
            return JsonResponse({'success': False, 'error': error_msg}, status=500)
            
        except Exception as e:
            error_msg = f"Error inesperado al resetear: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return JsonResponse({'success': False, 'error': error_msg}, status=500)
    
    return JsonResponse({'error': 'Método no permitido'}, status=405)