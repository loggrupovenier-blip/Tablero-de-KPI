import os
import sqlite3

# ── Detectar si usar PostgreSQL o SQLite ─────────────────────────────────────
DATABASE_URL = os.environ.get('DATABASE_URL', '')

if DATABASE_URL:
    import psycopg2
    import psycopg2.extras
    USE_PG = True
else:
    USE_PG = False
    DB_NAME = 'kpi.db'


def get_conn():
    if USE_PG:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    else:
        return sqlite3.connect(DB_NAME)


def ph(n=1):
    """Placeholder: %s para postgres, ? para sqlite."""
    if USE_PG:
        return ', '.join(['%s'] * n)
    return ', '.join(['?'] * n)


def P():
    """Placeholder único."""
    return '%s' if USE_PG else '?'


def adapt_query(q):
    """Convierte ? a %s si estamos en postgres."""
    if USE_PG:
        return q.replace('?', '%s')
    return q


def fetchall_as_dicts(cursor):
    if USE_PG:
        return cursor.fetchall()
    return cursor.fetchall()


def init_db():
    conn = get_conn()
    c = conn.cursor()

    if USE_PG:
        c.execute('''CREATE TABLE IF NOT EXISTS maestro_kpi (
            id SERIAL PRIMARY KEY,
            codigo TEXT,
            descripcion TEXT,
            duenio TEXT,
            unidad TEXT,
            calculo TEXT,
            polaridad TEXT,
            definicion TEXT,
            objetivo TEXT,
            forma_calculo TEXT,
            excluye TEXT,
            periodicidad TEXT,
            fuente_info TEXT,
            tipo TEXT DEFAULT 'kpi',
            orden INTEGER DEFAULT 0,
            es_critico TEXT DEFAULT 'no'
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS valores (
            id SERIAL PRIMARY KEY,
            kpi_id INTEGER,
            fecha TEXT,
            tipo TEXT,
            valor REAL,
            FOREIGN KEY(kpi_id) REFERENCES maestro_kpi(id)
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS kpi_periodos_activos (
            id SERIAL PRIMARY KEY,
            kpi_id INTEGER,
            fecha_inicio TEXT,
            fecha_fin TEXT,
            FOREIGN KEY(kpi_id) REFERENCES maestro_kpi(id)
        )''')

        c.execute("SELECT COUNT(*) FROM maestro_kpi WHERE tipo='kpi'")
        if c.fetchone()[0] == 0:
            c.execute('''INSERT INTO maestro_kpi
                (codigo, descripcion, duenio, unidad, calculo, polaridad, tipo, orden,
                 definicion, objetivo, forma_calculo, excluye, periodicidad, fuente_info, es_critico)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                ('1.1', 'Lesiones con tarea modificada', 'Ref Seguridad', '#', 'suma', '▼', 'kpi', 0,
                 'Número de lesiones que modifican tarea', 'Reducir a 0', 'Suma de eventos',
                 'Ninguna', 'diaria', 'Registro interno', 'no'))

    else:
        c.execute('''CREATE TABLE IF NOT EXISTS maestro_kpi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT,
            descripcion TEXT,
            duenio TEXT,
            unidad TEXT,
            calculo TEXT,
            polaridad TEXT,
            definicion TEXT,
            objetivo TEXT,
            forma_calculo TEXT,
            excluye TEXT,
            periodicidad TEXT,
            fuente_info TEXT,
            tipo TEXT DEFAULT 'kpi',
            orden INTEGER DEFAULT 0,
            es_critico TEXT DEFAULT 'no'
        )''')

        c.execute("PRAGMA table_info(maestro_kpi)")
        columnas = [col[1] for col in c.fetchall()]
        for col, defval in [('tipo', "'kpi'"), ('orden', '0'), ('es_critico', "'no'")]:
            if col not in columnas:
                c.execute(f"ALTER TABLE maestro_kpi ADD COLUMN {col} TEXT DEFAULT {defval}")

        c.execute('''CREATE TABLE IF NOT EXISTS valores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kpi_id INTEGER,
            fecha TEXT,
            tipo TEXT,
            valor REAL,
            FOREIGN KEY(kpi_id) REFERENCES maestro_kpi(id)
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS kpi_periodos_activos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kpi_id INTEGER,
            fecha_inicio TEXT,
            fecha_fin TEXT,
            FOREIGN KEY(kpi_id) REFERENCES maestro_kpi(id)
        )''')

        c.execute("SELECT COUNT(*) FROM maestro_kpi WHERE tipo='kpi'")
        if c.fetchone()[0] == 0:
            c.execute('''INSERT INTO maestro_kpi
                (codigo, descripcion, duenio, unidad, calculo, polaridad, tipo, orden,
                 definicion, objetivo, forma_calculo, excluye, periodicidad, fuente_info, es_critico)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                ('1.1', 'Lesiones con tarea modificada', 'Ref Seguridad', '#', 'suma', '▼', 'kpi', 0,
                 'Número de lesiones que modifican tarea', 'Reducir a 0', 'Suma de eventos',
                 'Ninguna', 'diaria', 'Registro interno', 'no'))

    conn.commit()
    conn.close()


def _row_to_elem(row):
    return {
        'id': row[0],
        'codigo': row[1] or '',
        'descripcion': row[2] or '',
        'duenio': row[3] or '',
        'unidad': row[4] or '',
        'calculo': row[5] or '',
        'polaridad': row[6] or '',
        'definicion': row[7] or '',
        'objetivo': row[8] or '',
        'forma_calculo': row[9] or '',
        'excluye': row[10] or '',
        'periodicidad': row[11] or '',
        'fuente_info': row[12] or '',
        'tipo': row[13] or 'kpi',
        'orden': row[14] or 0,
        'es_critico': row[15] if len(row) > 15 else 'no'
    }


def get_elementos_ordenados():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM maestro_kpi ORDER BY orden, id")
    rows = c.fetchall()
    conn.close()
    return [_row_to_elem(r) for r in rows]


def get_valores(kpi_id, year):
    conn = get_conn()
    c = conn.cursor()
    start = f"{year}-01-01"
    end = f"{year}-12-31"
    c.execute(adapt_query(
        "SELECT fecha, tipo, valor FROM valores WHERE kpi_id=? AND fecha BETWEEN ? AND ?"),
        (kpi_id, start, end))
    obj, real, gatillo = {}, {}, {}
    for fecha, tipo, valor in c.fetchall():
        if tipo == 'obj':
            obj[fecha] = valor
        elif tipo == 'real':
            real[fecha] = valor
        elif tipo == 'gatillo':
            gatillo[fecha] = valor
    conn.close()
    return obj, real, gatillo


def set_valor(kpi_id, fecha, tipo, valor):
    conn = get_conn()
    c = conn.cursor()
    c.execute(adapt_query("DELETE FROM valores WHERE kpi_id=? AND fecha=? AND tipo=?"),
              (kpi_id, fecha, tipo))
    if valor is not None and valor != '':
        c.execute(adapt_query(
            "INSERT INTO valores (kpi_id, fecha, tipo, valor) VALUES (?,?,?,?)"),
            (kpi_id, fecha, tipo, float(valor)))
    conn.commit()
    conn.close()


def agregar_elemento(data):
    conn = get_conn()
    c = conn.cursor()
    if data.get('tipo', 'kpi') == 'kpi':
        c.execute(adapt_query(
            "SELECT id FROM maestro_kpi WHERE codigo=? AND tipo='kpi'"), (data['codigo'],))
        if c.fetchone():
            conn.close()
            raise ValueError("El código ya existe")
    c.execute("SELECT MAX(orden) FROM maestro_kpi")
    max_orden = c.fetchone()[0] or 0
    nuevo_orden = max_orden + 1
    if USE_PG:
        c.execute('''INSERT INTO maestro_kpi
            (codigo, descripcion, duenio, unidad, calculo, polaridad, definicion, objetivo,
             forma_calculo, excluye, periodicidad, fuente_info, tipo, orden, es_critico)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
            (data.get('codigo'), data.get('descripcion'), data.get('duenio'), data.get('unidad'),
             data.get('calculo'), data.get('polaridad'), data.get('definicion', ''),
             data.get('objetivo', ''), data.get('forma_calculo', ''), data.get('excluye', ''),
             data.get('periodicidad', ''), data.get('fuente_info', ''), data.get('tipo', 'kpi'),
             nuevo_orden, data.get('es_critico', 'no')))
        new_id = c.fetchone()[0]
    else:
        c.execute('''INSERT INTO maestro_kpi
            (codigo, descripcion, duenio, unidad, calculo, polaridad, definicion, objetivo,
             forma_calculo, excluye, periodicidad, fuente_info, tipo, orden, es_critico)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (data.get('codigo'), data.get('descripcion'), data.get('duenio'), data.get('unidad'),
             data.get('calculo'), data.get('polaridad'), data.get('definicion', ''),
             data.get('objetivo', ''), data.get('forma_calculo', ''), data.get('excluye', ''),
             data.get('periodicidad', ''), data.get('fuente_info', ''), data.get('tipo', 'kpi'),
             nuevo_orden, data.get('es_critico', 'no')))
        new_id = c.lastrowid
    conn.commit()
    conn.close()
    return new_id


def actualizar_elemento(elemento_id, data):
    conn = get_conn()
    c = conn.cursor()
    if data.get('tipo', 'kpi') == 'kpi' and 'codigo' in data:
        c.execute(adapt_query(
            "SELECT id FROM maestro_kpi WHERE codigo=? AND tipo='kpi' AND id != ?"),
            (data['codigo'], elemento_id))
        if c.fetchone():
            conn.close()
            raise ValueError("El código ya existe")
    c.execute(adapt_query('''UPDATE maestro_kpi SET
        codigo=?, descripcion=?, duenio=?, unidad=?, calculo=?, polaridad=?,
        definicion=?, objetivo=?, forma_calculo=?, excluye=?, periodicidad=?,
        fuente_info=?, tipo=?, es_critico=?
        WHERE id=?'''),
        (data.get('codigo'), data.get('descripcion'), data.get('duenio'), data.get('unidad'),
         data.get('calculo'), data.get('polaridad'), data.get('definicion', ''),
         data.get('objetivo', ''), data.get('forma_calculo', ''), data.get('excluye', ''),
         data.get('periodicidad', ''), data.get('fuente_info', ''), data.get('tipo', 'kpi'),
         data.get('es_critico', 'no'), elemento_id))
    conn.commit()
    conn.close()


def eliminar_elemento(elemento_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(adapt_query("DELETE FROM valores WHERE kpi_id=?"), (elemento_id,))
    c.execute(adapt_query("DELETE FROM maestro_kpi WHERE id=?"), (elemento_id,))
    conn.commit()
    conn.close()


def insertar_separador_despues_de(elemento_id, titulo="---"):
    conn = get_conn()
    c = conn.cursor()
    c.execute(adapt_query("SELECT orden FROM maestro_kpi WHERE id=?"), (elemento_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return
    orden_ref = row[0]
    c.execute(adapt_query("UPDATE maestro_kpi SET orden = orden + 1 WHERE orden > ?"), (orden_ref,))
    nuevo_orden = orden_ref + 1
    c.execute(adapt_query('''INSERT INTO maestro_kpi
        (codigo, descripcion, duenio, unidad, calculo, polaridad, definicion, objetivo,
         forma_calculo, excluye, periodicidad, fuente_info, tipo, orden, es_critico)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)'''),
        (None, titulo, '', '', '', '', '', '', '', '', '', '', 'separador', nuevo_orden, 'no'))
    conn.commit()
    conn.close()


def reordenar_elementos(ordenes):
    conn = get_conn()
    c = conn.cursor()
    for item in ordenes:
        c.execute(adapt_query("UPDATE maestro_kpi SET orden = ? WHERE id = ?"),
                  (item['orden'], item['id']))
    conn.commit()
    conn.close()


def obtener_elemento_por_id(elemento_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(adapt_query("SELECT * FROM maestro_kpi WHERE id=?"), (elemento_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return _row_to_elem(row)
    return None


def get_periodos_activos(kpi_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(adapt_query(
        "SELECT id, fecha_inicio, fecha_fin FROM kpi_periodos_activos WHERE kpi_id=? ORDER BY fecha_inicio"),
        (kpi_id,))
    rows = c.fetchall()
    conn.close()
    return [{'id': r[0], 'fecha_inicio': r[1], 'fecha_fin': r[2]} for r in rows]


def agregar_periodo_activo(kpi_id, fecha_inicio, fecha_fin):
    conn = get_conn()
    c = conn.cursor()
    if USE_PG:
        c.execute(
            "INSERT INTO kpi_periodos_activos (kpi_id, fecha_inicio, fecha_fin) VALUES (%s,%s,%s) RETURNING id",
            (kpi_id, fecha_inicio, fecha_fin))
        new_id = c.fetchone()[0]
    else:
        c.execute(
            "INSERT INTO kpi_periodos_activos (kpi_id, fecha_inicio, fecha_fin) VALUES (?,?,?)",
            (kpi_id, fecha_inicio, fecha_fin))
        new_id = c.lastrowid
    conn.commit()
    conn.close()
    return new_id


def eliminar_periodo_activo(periodo_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(adapt_query("DELETE FROM kpi_periodos_activos WHERE id=?"), (periodo_id,))
    conn.commit()
    conn.close()


def kpi_activo_en_rango(kpi_id, fecha_inicio_str, fecha_fin_str):
    conn = get_conn()
    c = conn.cursor()
    c.execute(adapt_query("SELECT COUNT(*) FROM kpi_periodos_activos WHERE kpi_id=?"), (kpi_id,))
    total = c.fetchone()[0]
    if total == 0:
        conn.close()
        return True
    c.execute(adapt_query(
        "SELECT COUNT(*) FROM kpi_periodos_activos WHERE kpi_id=? AND fecha_inicio <= ? AND fecha_fin >= ?"),
        (kpi_id, fecha_fin_str, fecha_inicio_str))
    activo = c.fetchone()[0] > 0
    conn.close()
    return activo