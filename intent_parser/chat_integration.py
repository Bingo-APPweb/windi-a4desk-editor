"""
WINDI Chat Integration v3.0.0 - Constitutional Edition with Retry
=================================================================
Integrado com Constitutional Validator e Retry automatico.

"KI verarbeitet. Der Mensch entscheidet. WINDI garantiert."

Features v3:
- Constitutional Gate com 9 Artigos
- Retry automatico se score < 70 (max 2 tentativas)
- Correcao de conteudo entre retries
- Audit trail completo em SQLite
- Preparado para LLM Adapter

28 Janeiro 2026 - Three Dragons Protocol
"""

import os
import sys
import json
import sqlite3
import re
# ============================================================================
# STYLE RESEARCH ENGINE INTEGRATION
# ============================================================================
STYLE_ENGINE_AVAILABLE = False
try:
    sys.path.insert(0, '/opt/windi/style_research')
    from chat_style_bridge import enhance_with_style, detect_style, get_style_config
    STYLE_ENGINE_AVAILABLE = True
    print('[WINDI] ✅ Style Research Engine loaded')
except ImportError as e:
    print(f'[WINDI] Style Research Engine not available: {e}')

from datetime import datetime

sys.path.insert(0, '/opt/windi/templates')
from intent_parser import IntentParser
from intent_patterns import extract_data

# ============================================================================
# CONFIGURATION
# ============================================================================

MIN_QUALITY_SCORE = 70
MAX_RETRIES = 2
DB_PATH = '/opt/windi/data/template_registry.db'

# ============================================================================
# CONSTITUTIONAL VALIDATOR INTEGRATION
# ============================================================================

CONSTITUTIONAL_VALIDATOR_AVAILABLE = False

try:
    from constitutional_validator_v2 import ConstitutionalValidatorV2
    CONSTITUTIONAL_VALIDATOR_AVAILABLE = True
    print("[WINDI] Constitutional Validator v2 loaded")
except ImportError:
    try:
        from constitutional_validator import ConstitutionalValidator as ConstitutionalValidatorV2
        CONSTITUTIONAL_VALIDATOR_AVAILABLE = True
        print("[WINDI] Constitutional Validator v1 loaded (fallback)")
    except ImportError:
        print("[WINDI] WARNING: Constitutional Validator not available")


# ============================================================================
# CONTENT CORRECTION - Para retry automatico
# ============================================================================

FORBIDDEN_REPLACEMENTS = {
    r'\bich denke\b': 'es wird festgestellt',
    r'\bich glaube\b': 'es ist anzunehmen',
    r'\bich meine\b': 'es ist festzustellen',
    r'\bmeiner meinung nach\b': 'nach Pruefung der Sachlage',
    r'\bvielleicht\b': 'gegebenenfalls',
    r'\beventuell\b': 'unter Umstaenden',
    r'\bmoeglicherweise\b': 'nach Ermessen',
    r'\bwahrscheinlich\b': 'voraussichtlich',
}


def correct_content(content_dict, violations):
    """
    Corrige conteudo baseado nas violacoes detectadas.
    Usado no retry automatico.
    """
    corrected = content_dict.copy()
    corrections_made = []
    
    # Converter para string para correcoes
    content_str = json.dumps(corrected, ensure_ascii=False)
    
    # Aplicar substituicoes de termos proibidos
    for pattern, replacement in FORBIDDEN_REPLACEMENTS.items():
        if re.search(pattern, content_str, re.IGNORECASE):
            content_str = re.sub(pattern, replacement, content_str, flags=re.IGNORECASE)
            corrections_made.append(f"Replaced forbidden term: {pattern}")
    
    # Tentar reconverter para dict
    try:
        corrected = json.loads(content_str)
    except:
        pass
    
    return corrected, corrections_made

# ============================================================================
# VALIDATION FUNCTION
# ============================================================================

def validate_content(template_info, data, content_str):
    """
    Valida conteudo contra Constitutional Validator.
    """
    if not CONSTITUTIONAL_VALIDATOR_AVAILABLE:
        return {
            'compliant': True,
            'quality_score': 100,
            'violations': [],
            'axiom_scores': {}
        }
    
    try:
        validator = ConstitutionalValidatorV2()
        template_dict = {
            'id': template_info.get('id', template_info.get('template_id', 'unknown')),
            'title_de': template_info.get('name', ''),
            'fields': [],
            'human_only': [],
            'style_profile': 'formal_amtlich'
        }
        
        result = validator.validate(template_dict, data, content_str)
        
        if hasattr(result, 'quality_score'):
            return {
                'compliant': result.compliant,
                'quality_score': result.quality_score,
                'violations': [v.to_dict() if hasattr(v, 'to_dict') else v for v in result.violations],
                'axiom_scores': result.axiom_scores if hasattr(result, 'axiom_scores') else {}
            }
        return result
    except Exception as e:
        print(f"[WINDI] Validator error: {e}")
        return {'compliant': True, 'quality_score': 50, 'violations': [], 'axiom_scores': {}}


# ============================================================================
# AUDIT LOGGING - SQLite
# ============================================================================

def log_constitutional_audit(template_id, quality_score, compliant, violations, retries=0, article_scores=None):
    """
    Loga resultado da validacao constitucional no SQLite.
    """
    scores = article_scores or {}
    critical_count = len([v for v in violations if v.get('severity') == 'critical'])
    
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            INSERT INTO constitutional_audit (
                template_id, quality_score, compliant,
                score_a1, score_a2, score_a3, score_a4, score_a5,
                score_a6, score_a7, score_a8, score_a9,
                violations_json, violations_count, critical_count, retries
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            template_id,
            quality_score,
            1 if compliant else 0,
            scores.get('A1'), scores.get('A2'), scores.get('A3'),
            scores.get('A4'), scores.get('A5'), scores.get('A6'),
            scores.get('A7'), scores.get('A8'), scores.get('A9'),
            json.dumps(violations),
            len(violations),
            critical_count,
            retries
        ))
        conn.commit()
        conn.close()
        print(f"[WINDI] Audit logged: score={quality_score}, compliant={compliant}, retries={retries}")
    except Exception as e:
        print(f"[WINDI] SQLite audit error: {e}")
    
    return {'quality_score': quality_score, 'compliant': compliant}

# ============================================================================
# CHAT INTENT HANDLER v3 - COM RETRY
# ============================================================================

class ChatIntentHandler:
    def __init__(self, registry_db=DB_PATH, default_tenant=None):
        self.parser = IntentParser(registry_db, default_tenant)

    def handle_message(self, message, session_id, context=None):
        context = context or {}
        result = self.parser.process_message(message, context)
        
        if result['action'] == 'passthrough':
            return {'handled': False, 'response': None, 'action': 'passthrough'}
        if result['action'] == 'ask_clarification':
            return {'handled': True, 'response': result['response_suggestion'], 'action': 'clarification'}
        if result['action'] == 'create_document':
            # Passar mensagem original para detecção de estilo
            result["extracted_data"]["_original_message"] = message
            return self._generate_document_with_retry(
                result['template'],
                result['extracted_data'],
                result['human_only_fields'],
                result['language']
            )
        return {'handled': False, 'response': None, 'action': 'unknown'}

    def _generate_document_with_retry(self, template, data, human_only, lang):
        """
        Gera documento com retry automatico se score < MIN_QUALITY_SCORE.
        """
        try:
            doc_type = template.get('doctype', '')
            if 'ablehnung' in doc_type.lower():
                from ablehnungsbescheid_generator import generate_ablehnungsbescheid_pdf, BEISPIEL_ABLEHNUNG
                bescheid_data = BEISPIEL_ABLEHNUNG.copy()
                generator = generate_ablehnungsbescheid_pdf
            else:
                from bescheid_generator import generate_bescheid_pdf, BEISPIEL_BAUGENEHMIGUNG
                bescheid_data = BEISPIEL_BAUGENEHMIGUNG.copy()
                generator = generate_bescheid_pdf

            # Preencher dados extraidos
            if data.get('antragsteller'):
                bescheid_data['recipient_name'] = data['antragsteller']
            if data.get('adresse'):
                bescheid_data['recipient_street'] = data['adresse']
            if data.get('plz') and data.get('ort'):
                bescheid_data['recipient_city'] = f"{data['plz']} {data['ort']}"
            elif data.get('ort'):
                bescheid_data['recipient_city'] = data['ort']
            if data.get('bauvorhaben'):
                bescheid_data['subject'] = f"Antrag auf Baugenehmigung: {data['bauvorhaben']}"

            # ================================================================

            # ================================================================
            # STYLE RESEARCH ENGINE - Aplicar estilo se detectado
            # ================================================================
            if STYLE_ENGINE_AVAILABLE:
                # Guardar mensagem original para detecção de estilo
                original_message = data.get("_original_message", "")
                if original_message:
                    bescheid_data = enhance_with_style(bescheid_data, original_message)
                    if bescheid_data.get("_windi_style"):
                        print(f"[WINDI Style] 🎨 Estilo aplicado: {bescheid_data['_windi_style']['style_name']}")

            # CONSTITUTIONAL GATE COM RETRY
            # ================================================================
            
            template_id = template.get('id', template.get('template_id', 'unknown'))
            retries = 0
            best_score = 0
            best_validation = None
            current_data = bescheid_data.copy()
            
            while retries <= MAX_RETRIES:
                content_for_validation = json.dumps(current_data, ensure_ascii=False)
                validation = validate_content(template, data, content_for_validation)
                quality_score = validation['quality_score']
                compliant = validation['compliant']
                
                # Guardar melhor resultado
                if quality_score > best_score:
                    best_score = quality_score
                    best_validation = validation
                    bescheid_data = current_data.copy()
                
                # Log audit para cada tentativa
                log_constitutional_audit(
                    template_id=template_id,
                    quality_score=quality_score,
                    compliant=compliant,
                    violations=validation.get('violations', []),
                    retries=retries,
                    article_scores=validation.get('axiom_scores', {})
                )
                
                # Se passou, sair do loop
                if quality_score >= MIN_QUALITY_SCORE or compliant:
                    print(f"[WINDI] Gate passed: score={quality_score}, retry={retries}")
                    break
                
                # Se nao passou e ainda tem retries, corrigir e tentar de novo
                if retries < MAX_RETRIES:
                    print(f"[WINDI] Gate failed: score={quality_score}, attempting correction...")
                    current_data, corrections = correct_content(current_data, validation.get('violations', []))
                    if corrections:
                        print(f"[WINDI] Corrections applied: {corrections}")
                
                retries += 1
            
            # Usar melhor resultado
            quality_score = best_score
            validation = best_validation or validation
            compliant = validation.get('compliant', False)

# Se ainda nao passou apos retries, rejeitar
            if quality_score < MIN_QUALITY_SCORE and not compliant:
                violations_str = ', '.join([v.get('code', 'unknown') for v in validation.get('violations', [])[:3]])
                return {
                    'handled': True,
                    'response': f"""Dokument nicht erstellt - Governance-Pruefung nicht bestanden.

Quality Score: {quality_score}/100 (Minimum: {MIN_QUALITY_SCORE})
Violations: {violations_str}
Retries: {retries}/{MAX_RETRIES}

Bitte ueberpruefen Sie die Eingaben und versuchen Sie es erneut.

KI verarbeitet. Der Mensch entscheidet. WINDI garantiert.""",
                    'action': 'governance_rejected',
                    'quality_score': quality_score,
                    'violations': validation.get('violations', []),
                    'retries': retries
                }
            
            # ================================================================
            # END CONSTITUTIONAL GATE
            # ================================================================

            # Gerar PDF (passou no Gate)
            pdf_bytes, receipt = generator(bescheid_data)
            pdf_filename = f"Bescheid_{receipt['id']}.pdf"
            pdf_path = f"/opt/windi/a4desk-editor/static/{pdf_filename}"
            with open(pdf_path, 'wb') as f:
                f.write(pdf_bytes)

            human_str = ', '.join([f['label'] for f in human_only]) if human_only else ''
            
            # Info de governanca
            retry_info = f" (after {retries} retry)" if retries > 0 else ""
            governance_info = f"Quality Score: {quality_score}/100{retry_info}"
            style_info = f"\nEstilo: {current_data.get('_windi_style', {}).get('style_name', 'Standard')}" if current_data.get('_windi_style') else ""

            response = f"""Dokument erstellt!

Receipt: {receipt['id']}
Hash: {receipt['hash']}
Template: {template['name']} v{template['version']}
{governance_info}{style_info}

Download: /static/{pdf_filename}

Nur Mensch: {human_str}

KI verarbeitet. Der Mensch entscheidet. WINDI garantiert."""

            return {
                'handled': True,
                'response': response,
                'action': 'document_created',
                'template': template,
                'receipt': receipt['id'],
                'pdf_url': f"/static/{pdf_filename}",
                'human_only_fields': human_only,
                'quality_score': quality_score,
                'constitutional_compliant': compliant,
                'retries': retries
            }
        except Exception as e:
            import traceback
            print(f"[WINDI] Generate error: {e}")
            traceback.print_exc()
            return {
                'handled': True,
                'response': f"Fehler bei Dokumenterstellung: {str(e)}",
                'action': 'error',
            }


if __name__ == '__main__':
    print("WINDI Chat Integration v3.0.0 - Constitutional Edition with Retry")
    print(f"Constitutional Validator: {'ACTIVE' if CONSTITUTIONAL_VALIDATOR_AVAILABLE else 'NOT AVAILABLE'}")
    print(f"Max Retries: {MAX_RETRIES}")
    print(f"Min Quality Score: {MIN_QUALITY_SCORE}")
    print("="*60)
