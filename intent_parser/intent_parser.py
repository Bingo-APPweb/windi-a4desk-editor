"""
WINDI Intent Parser v1.0.0
"""

from datetime import datetime
from intent_patterns import parse_intent, detect_language
from intent_registry_bridge import get_bridge

class IntentParser:
    def __init__(self, registry_db=None, default_tenant=None):
        self.bridge = get_bridge(registry_db)
        self.default_tenant = default_tenant
    
    def process_message(self, message, context=None):
        context = context or {}
        intent = parse_intent(message)
        
        result = {
            'action': 'passthrough',
            'intent': intent,
            'template': None,
            'extracted_data': intent.get('extracted_data', {}),
            'missing_fields': [],
            'human_only_fields': [],
            'response_suggestion': None,
            'language': intent.get('language', 'de'),
        }
        
        if not intent.get('has_create_intent'):
            return result
        
        doc_type = intent.get('document_type')
        department = intent.get('department')
        
        if not doc_type:
            result['action'] = 'ask_clarification'
            result['response_suggestion'] = self._ask_doc_type(intent['language'])
            return result
        
        template = self.bridge.find_template(doc_type, department)
        
        if not template:
            result['action'] = 'ask_clarification'
            available = self.bridge.list_available_templates()
            result['response_suggestion'] = self._template_not_found(doc_type, available, intent['language'])
            return result
        
        result['template'] = template
        result['human_only_fields'] = self.bridge.get_human_only_fields(template['template_id'])
        
        result['action'] = 'create_document'
        result['response_suggestion'] = self._confirm_create(
            template, intent['extracted_data'], result['human_only_fields'], intent['language']
        )
        return result
    
    def _ask_doc_type(self, lang):
        msgs = {
            'de': 'Welche Art von Bescheid? (Baugenehmigung, Ablehnungsbescheid, etc.)',
            'en': 'What type of document? (Building permit, Rejection, etc.)',
            'pt': 'Que tipo de documento? (Licenca de construcao, Rejeicao, etc.)',
        }
        return msgs.get(lang, msgs['de'])
    
    def _template_not_found(self, doc_type, available, lang):
        if not available:
            return f'Kein Template fuer "{doc_type}" gefunden.'
        names = ', '.join([t['name'] for t in available[:3]])
        return f'Template "{doc_type}" nicht gefunden. Verfuegbar: {names}'
    
    def _confirm_create(self, template, data, human_only, lang):
        name = template['name']
        data_str = ', '.join([f"{k}: {v}" for k, v in data.items()]) if data else 'keine'
        human_str = ', '.join([f['label'] for f in human_only]) if human_only else 'keine'
        
        msgs = {
            'de': f'Erstelle {name}.\nDaten: {data_str}\nNoch auszufuellen: {human_str}',
            'en': f'Creating {name}.\nData: {data_str}\nTo fill: {human_str}',
            'pt': f'Criando {name}.\nDados: {data_str}\nPreencher: {human_str}',
        }
        return msgs.get(lang, msgs['de'])

def process_chat_message(message, context=None):
    parser = IntentParser()
    return parser.process_message(message, context)

if __name__ == '__main__':
    r = process_chat_message("Erstellen Sie einen Bescheid Baugenehmigung")
    print(f"Action: {r['action']}")
    print(f"Template: {r['template']}")
    print(f"Response: {r['response_suggestion']}")
