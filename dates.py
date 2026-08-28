from datetime import datetime, timedelta

MESES_ES = [
    'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'
]
MESES_ES_CAP = [m.capitalize() for m in MESES_ES]

DIAS_ES = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

def nombre_mes_espanol(fecha):
    return MESES_ES[fecha.month - 1]

def generar_dias_ano(year, excluir_domingos=True):
    start = datetime(year, 1, 1)
    end = datetime(year, 12, 31)
    dias = []
    while start <= end:
        if not excluir_domingos or start.weekday() != 6:
            dias.append(start)
        start += timedelta(days=1)
    return dias

def agrupar_por_semana(dias):
    semanas = []
    semana_actual = []
    for dia in dias:
        if not semana_actual:
            semana_actual.append(dia)
        else:
            if dia.weekday() == 0:
                semanas.append((semana_actual[0], semana_actual[-1], semana_actual))
                semana_actual = [dia]
            else:
                semana_actual.append(dia)
    if semana_actual:
        semanas.append((semana_actual[0], semana_actual[-1], semana_actual))
    return semanas

def agrupar_por_mes(dias):
    meses = {}
    for dia in dias:
        key = (dia.year, dia.month)
        if key not in meses:
            meses[key] = []
        meses[key].append(dia)
    resultado = []
    for (year, month), dias_list in sorted(meses.items()):
        resultado.append((year, month, dias_list))
    return resultado

def obtener_estructura_periodos(year, tipo_reunion):
    dias = generar_dias_ano(year, excluir_domingos=True)
    periodos = []
    if tipo_reunion == 'diaria':
        for dia in dias:
            nombre_dia_es = DIAS_ES[dia.weekday()]
            periodos.append({
                'nombre': dia.strftime('%d-%m-%Y'),
                'nombre_sub': nombre_dia_es,
                'fecha_inicio': dia,
                'fecha_fin': dia,
                'dias': [dia],
                'clase_mes': nombre_mes_espanol(dia)
            })
    elif tipo_reunion == 'semanal':
        semanas = agrupar_por_semana(dias)
        for inicio, fin, dias_list in semanas:
            num_semana = inicio.isocalendar()[1]
            nombre = f"Sem {num_semana} ({inicio.strftime('%d/%m')}-{fin.strftime('%d/%m')})"
            periodos.append({
                'nombre': nombre,
                'nombre_sub': '',  # Siempre string vacío para semanal
                'fecha_inicio': inicio,
                'fecha_fin': fin,
                'dias': dias_list,
                'clase_mes': nombre_mes_espanol(inicio)
            })
    else:  # mensual
        meses = agrupar_por_mes(dias)
        for year, month, dias_list in meses:
            nombre = MESES_ES_CAP[month-1] + f" {year}"
            periodos.append({
                'nombre': nombre,
                'nombre_sub': '',  # Siempre string vacío para mensual
                'fecha_inicio': dias_list[0],
                'fecha_fin': dias_list[-1],
                'dias': dias_list,
                'clase_mes': MESES_ES[month-1]
            })
    meses_set = set(p['clase_mes'] for p in periodos)
    meses_unicos_raw = sorted(meses_set, key=lambda m: MESES_ES.index(m))
    meses_unicos_display = [m.capitalize() for m in meses_unicos_raw]
    return periodos, meses_unicos_display
