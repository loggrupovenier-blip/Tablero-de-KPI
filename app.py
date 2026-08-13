import os
import webbrowser
from threading import Timer
from flask import Flask, render_template, request, jsonify, send_file
from datetime import datetime
import io
import csv
import json
from db import (
    init_db, get_elementos_ordenados, get_valores, set_valor,
    agregar_elemento, actualizar_elemento, eliminar_elemento,
    insertar_separador_despues_de, reordenar_elementos, obtener_elemento_por_id,
    get_periodos_activos, agregar_periodo_activo, eliminar_periodo_activo,
    kpi_activo_en_rango, get_valores_completos, importar_valores_masivos
)
from dates import obtener_estructura_periodos

app = Flask(__name__)

def calcular_valor_agregado(valores_diarios, calculo):
    """
    valores_diarios: lista de números (v_obj o v_real o v_gatillo)
    calculo: 'suma', 'promedio', 'maximo'
    Retorna el valor agregado o None.
    """
    if not valores_diarios:
        return None
    if calculo == 'suma':
        return sum(valores_diarios)
    elif calculo == 'promedio':
        return sum(valores_diarios) / len(valores_diarios)
    elif calculo == 'maximo':
        return max(valores_diarios)
    return None

def agregar_valores_periodo(kpi, periodo, valores_diarios_obj, valores_diarios_real, valores_diarios_gatillo):
    """
    Calcula obj, real, gatillo para un período (semanal/mensual) a partir de los diarios.
    """
    dias_del_periodo = periodo['dias']
    calculo = kpi['calculo']
    
    vals_obj = []
    vals_real = []
    vals_gatillo = []
    
    for dia in dias_del_periodo:
        dia_key = dia.date().isoformat()
        v_obj = valores_diarios_obj.get(dia_key)
        v_real = valores_diarios_real.get(dia_key)
        v_gat = valores_diarios_gatillo.get(dia_key)
        if v_obj is not None:
            vals_obj.append(v_obj)
        if v_real is not None:
            vals_real.append(v_real)
        if v_gat is not None:
            vals_gatillo.append(v_gat)
    
    obj_agregado = calcular_valor_agregado(vals_obj, calculo)
    real_agregado = calcular_valor_agregado(vals_real, calculo)
    gatillo_agregado = calcular_valor_agregado(vals_gatillo, calculo)
    
    return obj_agregado, real_agregado, gatillo_agregado

@app.route('/')
def index():
    return render_template('tablero.html')

@app.route('/maestro')
def maestro():
    return render_template('maestro.html')

@app.route('/api/tablero')
def api_tablero():
    # Obtener año actual si no se especifica
    year = int(request.args.get('year', datetime.now().year))
    tipo_reunion = request.args.get('tipo', 'diaria')
    periodos, meses_unicos = obtener_estructura_periodos(year, tipo_reunion)
    periodos_json = []
    for p in periodos:
        periodos_json.append({
            'nombre': p['nombre'],
            'nombre_sub': p.get('nombre_sub', ''),
            'fecha_inicio': p['fecha_inicio'].isoformat(),
            'fecha_fin': p['fecha_fin'].isoformat(),
            'dias': [d.isoformat() for d in p['dias']],
            'clase_mes': p['clase_mes']
        })
    
    elementos = get_elementos_ordenados()
    
    # Calcular rango de fechas visible en el tablero
    if periodos:
        rango_inicio = periodos[0]['fecha_inicio'].date().isoformat()
        rango_fin = periodos[-1]['fecha_fin'].date().isoformat()
    else:
        rango_inicio = rango_fin = f"{year}-01-01"

    # Filtrar KPIs por periodicidad y por períodos activos
    elementos_filtrados = []
    for elem in elementos:
        if elem['tipo'] == 'separador':
            elementos_filtrados.append(elem)
        elif elem['tipo'] == 'kpi':
            periodicidad_str = (elem.get('periodicidad') or '').strip().lower()
            if not periodicidad_str:
                pass  # sin periodicidad definida no aplica filtro de reunión
            else:
                periodicidades = [p.strip() for p in periodicidad_str.split(',') if p.strip()]
                if tipo_reunion not in periodicidades:
                    continue
            if not kpi_activo_en_rango(elem['id'], rango_inicio, rango_fin):
                continue
            elementos_filtrados.append(elem)
    
    kpis_filtrados = [e for e in elementos_filtrados if e['tipo'] == 'kpi']
    valores_obj = {}
    valores_real = {}
    valores_gatillo = {}
    
    for kpi in kpis_filtrados:
        obj_guardado, real_guardado, gatillo_guardado = get_valores(kpi['id'], year)
        obj_por_periodo = {}
        real_por_periodo = {}
        gatillo_por_periodo = {}
        
        if tipo_reunion == 'diaria':
            for p in periodos:
                fecha_key = p['fecha_inicio'].date().isoformat()
                obj_por_periodo[fecha_key] = obj_guardado.get(fecha_key, '')
                real_por_periodo[fecha_key] = real_guardado.get(fecha_key, '')
                gatillo_por_periodo[fecha_key] = gatillo_guardado.get(fecha_key, '')
        else:
            for p in periodos:
                obj_calc, real_calc, gatillo_calc = agregar_valores_periodo(
                    kpi, p, obj_guardado, real_guardado, gatillo_guardado
                )
                fecha_key = p['fecha_inicio'].date().isoformat()
                obj_por_periodo[fecha_key] = obj_calc if obj_calc is not None else ''
                real_por_periodo[fecha_key] = real_calc if real_calc is not None else ''
                gatillo_por_periodo[fecha_key] = gatillo_calc if gatillo_calc is not None else ''
        
        valores_obj[kpi['id']] = obj_por_periodo
        valores_real[kpi['id']] = real_por_periodo
        valores_gatillo[kpi['id']] = gatillo_por_periodo
    
    return jsonify({
        'periodos': periodos_json,
        'elementos': elementos_filtrados,
        'valoresObj': valores_obj,
        'valoresReal': valores_real,
        'valoresGatillo': valores_gatillo,
        'mesesUnicos': meses_unicos,
        'yearActual': datetime.now().year,
        'mesActual': datetime.now().month
    })

@app.route('/api/valor', methods=['POST'])
def save_valor():
    data = request.json
    set_valor(data['kpi_id'], data['fecha'], data['tipo'], data['valor'])
    return jsonify({'ok': True})

@app.route('/api/elementos', methods=['GET'])
def api_list_elementos():
    elementos = get_elementos_ordenados()
    return jsonify(elementos)

@app.route('/api/elemento/<int:elemento_id>', methods=['GET'])
def api_get_elemento(elemento_id):
    elem = obtener_elemento_por_id(elemento_id)
    return jsonify(elem)

@app.route('/api/elemento', methods=['POST'])
def api_create_elemento():
    data = request.json
    try:
        new_id = agregar_elemento(data)
        return jsonify({'id': new_id})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/elemento/<int:elemento_id>', methods=['PUT'])
def api_update_elemento(elemento_id):
    data = request.json
    try:
        actualizar_elemento(elemento_id, data)
        return jsonify({'ok': True})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/elemento/<int:elemento_id>', methods=['DELETE'])
def api_delete_elemento(elemento_id):
    eliminar_elemento(elemento_id)
    return jsonify({'ok': True})

@app.route('/api/separador', methods=['POST'])
def api_insertar_separador():
    data = request.json
    elemento_id = data.get('after_id')
    titulo = data.get('titulo', '---')
    if elemento_id:
        insertar_separador_despues_de(elemento_id, titulo)
    else:
        from db import agregar_elemento
        agregar_elemento({
            'tipo': 'separador',
            'descripcion': titulo,
            'codigo': None, 'duenio': '', 'unidad': '', 'calculo': '',
            'polaridad': '', 'definicion': '', 'objetivo': '', 'forma_calculo': '',
            'excluye': '', 'periodicidad': '', 'fuente_info': '', 'es_critico': 'no'
        })
    return jsonify({'ok': True})

@app.route('/api/reordenar', methods=['POST'])
def api_reordenar():
    ordenes = request.json.get('ordenes', [])
    reordenar_elementos(ordenes)
    return jsonify({'ok': True})

@app.route('/api/elemento/<int:kpi_id>/periodos', methods=['GET'])
def api_get_periodos(kpi_id):
    return jsonify(get_periodos_activos(kpi_id))

@app.route('/api/elemento/<int:kpi_id>/periodos', methods=['POST'])
def api_agregar_periodo(kpi_id):
    data = request.json
    new_id = agregar_periodo_activo(kpi_id, data['fecha_inicio'], data['fecha_fin'])
    return jsonify({'id': new_id})

@app.route('/api/periodo/<int:periodo_id>', methods=['DELETE'])
def api_eliminar_periodo(periodo_id):
    eliminar_periodo_activo(periodo_id)
    return jsonify({'ok': True})

# ── NUEVAS RUTAS PARA IMPORTAR/EXPORTAR ──────────────────────────────────────

@app.route('/api/exportar/maestro', methods=['GET'])
def exportar_maestro():
    """Exporta todos los elementos del maestro a CSV"""
    elementos = get_elementos_ordenados()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Cabeceras
    writer.writerow([
        'id', 'tipo', 'codigo', 'descripcion', 'duenio', 'unidad', 'calculo',
        'polaridad', 'definicion', 'objetivo', 'forma_calculo', 'excluye',
        'periodicidad', 'fuente_info', 'es_critico', 'orden'
    ])
    
    # Datos
    for elem in elementos:
        writer.writerow([
            elem['id'],
            elem['tipo'],
            elem['codigo'] or '',
            elem['descripcion'] or '',
            elem['duenio'] or '',
            elem['unidad'] or '',
            elem['calculo'] or '',
            elem['polaridad'] or '',
            elem['definicion'] or '',
            elem['objetivo'] or '',
            elem['forma_calculo'] or '',
            elem['excluye'] or '',
            elem['periodicidad'] or '',
            elem['fuente_info'] or '',
            elem['es_critico'] or 'no',
            elem['orden'] or 0
        ])
    
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='maestro_kpi.csv'
    )

@app.route('/api/exportar/valores', methods=['GET'])
def exportar_valores():
    """Exporta todos los valores a CSV"""
    # Obtener todos los valores (sin filtrar por año)
    kpis = get_elementos_ordenados()
    kpis_kpi = [k for k in kpis if k['tipo'] == 'kpi']
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Cabeceras
    writer.writerow(['kpi_id', 'codigo', 'descripcion', 'fecha', 'tipo', 'valor'])
    
    # Datos
    for kpi in kpis_kpi:
        # Obtener valores para todos los años
        for year in range(2020, 2031):  # Rango amplio de años
            obj, real, gatillo = get_valores(kpi['id'], year)
            
            # Procesar OBJ
            for fecha, valor in obj.items():
                if valor is not None and valor != '':
                    writer.writerow([
                        kpi['id'],
                        kpi['codigo'] or '',
                        kpi['descripcion'] or '',
                        fecha,
                        'obj',
                        valor
                    ])
            
            # Procesar REAL
            for fecha, valor in real.items():
                if valor is not None and valor != '':
                    writer.writerow([
                        kpi['id'],
                        kpi['codigo'] or '',
                        kpi['descripcion'] or '',
                        fecha,
                        'real',
                        valor
                    ])
            
            # Procesar GATILLO
            for fecha, valor in gatillo.items():
                if valor is not None and valor != '':
                    writer.writerow([
                        kpi['id'],
                        kpi['codigo'] or '',
                        kpi['descripcion'] or '',
                        fecha,
                        'gatillo',
                        valor
                    ])
    
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='valores_kpi.csv'
    )

@app.route('/api/importar/maestro', methods=['POST'])
def importar_maestro():
    """Importa elementos del maestro desde CSV"""
    if 'file' not in request.files:
        return jsonify({'error': 'No se envió ningún archivo'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Nombre de archivo vacío'}), 400
    
    try:
        content = file.read().decode('utf-8-sig')
        reader = csv.reader(io.StringIO(content))
        headers = next(reader)  # Saltar cabeceras
        
        elementos_importados = []
        errores = []
        
        # Obtener elementos existentes para evitar duplicados
        existentes = get_elementos_ordenados()
        codigos_existentes = [e['codigo'] for e in existentes if e['tipo'] == 'kpi' and e['codigo']]
        
        for row_num, row in enumerate(reader, start=2):
            if len(row) < 16:
                errores.append(f"Fila {row_num}: Número de columnas incorrecto ({len(row)} esperado 16)")
                continue
            
            try:
                elem_data = {
                    'tipo': row[1].strip() or 'kpi',
                    'codigo': row[2].strip() or None,
                    'descripcion': row[3].strip() or '',
                    'duenio': row[4].strip() or '',
                    'unidad': row[5].strip() or '',
                    'calculo': row[6].strip() or '',
                    'polaridad': row[7].strip() or '',
                    'definicion': row[8].strip() or '',
                    'objetivo': row[9].strip() or '',
                    'forma_calculo': row[10].strip() or '',
                    'excluye': row[11].strip() or '',
                    'periodicidad': row[12].strip() or '',
                    'fuente_info': row[13].strip() or '',
                    'es_critico': row[14].strip() or 'no',
                }
                
                # Validar
                if elem_data['tipo'] == 'kpi':
                    if not elem_data['codigo']:
                        errores.append(f"Fila {row_num}: El código es obligatorio para KPIs")
                        continue
                    if elem_data['codigo'] in codigos_existentes:
                        errores.append(f"Fila {row_num}: El código '{elem_data['codigo']}' ya existe")
                        continue
                    if not elem_data['descripcion']:
                        errores.append(f"Fila {row_num}: La descripción es obligatoria")
                        continue
                
                # Agregar el elemento
                new_id = agregar_elemento(elem_data)
                elementos_importados.append(new_id)
                
            except Exception as e:
                errores.append(f"Fila {row_num}: {str(e)}")
        
        return jsonify({
            'ok': True,
            'importados': len(elementos_importados),
            'errores': errores
        })
        
    except Exception as e:
        return jsonify({'error': f'Error al procesar el archivo: {str(e)}'}), 400

@app.route('/api/importar/valores', methods=['POST'])
def importar_valores():
    """Importa valores desde CSV"""
    if 'file' not in request.files:
        return jsonify({'error': 'No se envió ningún archivo'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Nombre de archivo vacío'}), 400
    
    try:
        content = file.read().decode('utf-8-sig')
        reader = csv.reader(io.StringIO(content))
        headers = next(reader)  # Saltar cabeceras
        
        # Obtener mapeo de códigos a IDs
        elementos = get_elementos_ordenados()
        codigo_to_id = {e['codigo']: e['id'] for e in elementos if e['tipo'] == 'kpi' and e['codigo']}
        
        valores_importados = 0
        errores = []
        
        for row_num, row in enumerate(reader, start=2):
            if len(row) < 6:
                errores.append(f"Fila {row_num}: Número de columnas incorrecto ({len(row)} esperado 6)")
                continue
            
            try:
                # Formato: kpi_id, codigo, descripcion, fecha, tipo, valor
                codigo = row[1].strip()
                fecha = row[3].strip()
                tipo = row[4].strip().lower()
                valor_str = row[5].strip()
                
                if not codigo or codigo not in codigo_to_id:
                    errores.append(f"Fila {row_num}: Código '{codigo}' no encontrado")
                    continue
                
                if not fecha:
                    errores.append(f"Fila {row_num}: Fecha vacía")
                    continue
                
                if tipo not in ['obj', 'real', 'gatillo']:
                    errores.append(f"Fila {row_num}: Tipo inválido '{tipo}' (debe ser obj, real o gatillo)")
                    continue
                
                try:
                    valor = float(valor_str) if valor_str else None
                except ValueError:
                    errores.append(f"Fila {row_num}: Valor '{valor_str}' no es numérico")
                    continue
                
                if valor is not None:
                    kpi_id = codigo_to_id[codigo]
                    set_valor(kpi_id, fecha, tipo, valor)
                    valores_importados += 1
                
            except Exception as e:
                errores.append(f"Fila {row_num}: {str(e)}")
        
        return jsonify({
            'ok': True,
            'importados': valores_importados,
            'errores': errores
        })
        
    except Exception as e:
        return jsonify({'error': f'Error al procesar el archivo: {str(e)}'}), 400

@app.route('/api/plantilla/maestro', methods=['GET'])
def plantilla_maestro():
    """Descarga plantilla para maestro KPI"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow([
        'id', 'tipo', 'codigo', 'descripcion', 'duenio', 'unidad', 'calculo',
        'polaridad', 'definicion', 'objetivo', 'forma_calculo', 'excluye',
        'periodicidad', 'fuente_info', 'es_critico', 'orden'
    ])
    
    # Ejemplo de KPI
    writer.writerow([
        '', 'kpi', '1.1', 'Lesiones con tarea modificada', 'Ref Seguridad', 
        '#', 'suma', '▼', 'Número de lesiones que modifican tarea', 
        'Reducir a 0', 'Suma de eventos', 'Ninguna', 'diaria', 'Registro interno', 'no', ''
    ])
    
    # Ejemplo de separador
    writer.writerow([
        '', 'separador', '', 'SEGURIDAD', '', '', '', '', '', '', '', '', '', '', '', ''
    ])
    
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='plantilla_maestro_kpi.csv'
    )

@app.route('/api/plantilla/valores', methods=['GET'])
def plantilla_valores():
    """Descarga plantilla para valores KPI"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(['kpi_id', 'codigo', 'descripcion', 'fecha', 'tipo', 'valor'])
    
    # Ejemplo de valores
    writer.writerow(['', '1.1', 'Lesiones con tarea modificada', '2026-01-01', 'obj', '0'])
    writer.writerow(['', '1.1', 'Lesiones con tarea modificada', '2026-01-01', 'real', '0'])
    writer.writerow(['', '1.1', 'Lesiones con tarea modificada', '2026-01-01', 'gatillo', '3'])
    
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='plantilla_valores_kpi.csv'
    )

if __name__ == '__main__':
    # Inicializar la base de datos
    init_db()
    
    # Obtener el puerto desde la variable de entorno (Render asigna uno)
    port = int(os.environ.get('PORT', 5000))
    
    # Detectar si estamos en producción o desarrollo
    is_production = os.environ.get('RENDER', False)
    
    if not is_production:
        # Solo abrir navegador en desarrollo local
        def abrir_navegador():
            webbrowser.open_new('http://127.0.0.1:5000')
        Timer(1, abrir_navegador).start()
    
    # Ejecutar la aplicación
    app.run(debug=not is_production, host='0.0.0.0', port=port)