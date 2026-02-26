import sqlite3
import os

REGISTRY_DB = '/opt/windi/data/template_registry.db'

class RegistryBridge:
    def __init__(self, db_path=None):
        self.db_path = db_path or REGISTRY_DB
    
    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def find_template(self, document_type, department=None, tenant_id=None):
        if not os.path.exists(self.db_path):
            return None
        conn = self._get_conn()
        try:
            query = """
                SELECT t.id, t.title_de, t.title_en, t.version, t.status,
                       d.name_de as department_name, d.code as department_code,
                       dt.name_de as doctype_name, dt.code as doctype_code,
                       ten.name as tenant_name
                FROM templates t
                JOIN departments d ON t.department_id = d.id
                JOIN doctypes dt ON t.doctype_id = dt.id
                JOIN tenants ten ON t.tenant_id = ten.id
                WHERE t.status = 'published'
                AND (LOWER(dt.code) LIKE ? OR LOWER(dt.name_de) LIKE ? OR LOWER(t.title_de) LIKE ?)
                ORDER BY t.published_at DESC LIMIT 1
            """
            search_term = "%" + document_type.lower() + "%"
            cursor = conn.execute(query, [search_term, search_term, search_term])
            row = cursor.fetchone()
            if row:
                return {
                    'template_id': row['id'],
                    'name': row['title_de'],
                    'version': row['version'],
                    'department': row['department_name'],
                    'doctype': row['doctype_name'],
                }
            return None
        finally:
            conn.close()
    
    def get_template_fields(self, template_id):
        if not os.path.exists(self.db_path):
            return {'ai_fillable': [], 'human_only': [], 'optional': []}
        conn = self._get_conn()
        try:
            cursor = conn.execute("""
                SELECT field_code, label_de, field_type, source, required
                FROM template_fields WHERE template_id = ?
                ORDER BY display_order
            """, (template_id,))
            result = {'ai_fillable': [], 'human_only': [], 'optional': []}
            for row in cursor.fetchall():
                info = {'name': row['field_code'], 'label': row['label_de'] or row['field_code']}
                if row['source'] == 'human_only':
                    result['human_only'].append(info)
                elif not row['required']:
                    result['optional'].append(info)
                else:
                    result['ai_fillable'].append(info)
            return result
        finally:
            conn.close()
    
    def get_human_only_fields(self, template_id):
        return self.get_template_fields(template_id)['human_only']
    
    def list_available_templates(self):
        if not os.path.exists(self.db_path):
            return []
        conn = self._get_conn()
        try:
            cursor = conn.execute("""
                SELECT t.id, t.title_de as name, t.version, d.name_de as department
                FROM templates t
                JOIN departments d ON t.department_id = d.id
                WHERE t.status = 'published'
            """)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

_bridge_instance = None

def get_bridge(db_path=None):
    global _bridge_instance
    if _bridge_instance is None or db_path:
        _bridge_instance = RegistryBridge(db_path)
    return _bridge_instance

if __name__ == '__main__':
    bridge = RegistryBridge()
    tpl = bridge.find_template('baugenehmigung')
    if tpl:
        print("Template:", tpl['name'])
        fields = bridge.get_template_fields(tpl['template_id'])
        print("Human-only:", [f['name'] for f in fields['human_only']])
