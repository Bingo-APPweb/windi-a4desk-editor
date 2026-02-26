"""
WINDI Intent Patterns v1.0.0
"""

import re
from typing import Dict, List, Tuple, Optional

CREATE_PATTERNS = {
    'de': [
        r'bescheid',
        r'neuen?\s+bescheid',
        r'bescheid\s+erstellen',
        r'genehmigung\s+erstellen',
        r'dokument\s+erstellen',
    ],
    'en': [
        r'create\s+.*(?:bescheid|permit|document)',
        r'generate\s+.*(?:permit|document)',
        r'building\s+permit',
    ],
    'pt': [
        r'criar\s+.*(?:bescheid|documento|licenca)',
        r'gerar\s+.*documento',
        r'licenca.*construcao',
    ]
}

DOCUMENT_TYPE_ALIASES = {
    'baugenehmigung': ['baugenehmigung', 'building permit', 'bauantrag'],
    'ablehnungsbescheid': ['ablehnung', 'rejection', 'denial'],
    'gebuehrenbescheid': ['gebuehr', 'fee', 'taxa'],
}

DEPARTMENT_ALIASES = {
    'bauamt': ['bauamt', 'building department'],
    'ordnungsamt': ['ordnungsamt', 'public order'],
    'finanzamt': ['finanzamt', 'finance'],
}

def detect_language(text):
    text_lower = text.lower()
    if any(w in text_lower for w in ['bescheid', 'erstellen', 'antrag']):
        return 'de'
    if any(w in text_lower for w in ['create', 'permit', 'building']):
        return 'en'
    if any(w in text_lower for w in ['criar', 'licenca', 'documento']):
        return 'pt'
    return 'de'

def detect_create_intent(text):
    text_lower = text.lower()
    for lang, patterns in CREATE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return True, lang
    return False, detect_language(text)

def detect_document_type(text):
    text_lower = text.lower()
    for doc_type, aliases in DOCUMENT_TYPE_ALIASES.items():
        for alias in aliases:
            if alias.lower() in text_lower:
                return doc_type
    if any(t in text_lower for t in ['bau', 'building', 'haus', 'garage']):
        return 'baugenehmigung'
    return None

def detect_department(text):
    text_lower = text.lower()
    for dept, aliases in DEPARTMENT_ALIASES.items():
        for alias in aliases:
            if alias.lower() in text_lower:
                return dept
    return None

def extract_data(text):
    extracted = {}
    m = re.search(r'antragsteller[:\s]+([A-Za-z\s\-]+?)(?:,|\.|\n|$)', text, re.I)
    if m:
        extracted['antragsteller'] = m.group(1).strip()
    m = re.search(r'([A-Za-z\-]+(?:strasse|str\.|weg|platz)\s*\d+)', text, re.I)
    if m:
        extracted['adresse'] = m.group(1).strip()
    m = re.search(r'(\d{5})\s+([A-Za-z\s\-]+?)(?:,|\.|\n|$)', text)
    if m:
        extracted['plz'] = m.group(1)
        extracted['ort'] = m.group(2).strip()
    return extracted

def parse_intent(text):
    is_create, lang = detect_create_intent(text)
    result = {
        'has_create_intent': is_create,
        'language': lang,
        'document_type': None,
        'department': None,
        'extracted_data': {},
        'confidence': 0.0,
    }
    if is_create:
        result['document_type'] = detect_document_type(text)
        result['department'] = detect_department(text)
        result['extracted_data'] = extract_data(text)
        conf = 0.3
        if result['document_type']:
            conf += 0.3
        if result['department']:
            conf += 0.2
        if result['extracted_data']:
            conf += 0.2
        result['confidence'] = min(1.0, conf)
    return result

if __name__ == '__main__':
    t = "Erstellen Sie einen Bescheid Baugenehmigung"
    r = parse_intent(t)
    print(f"Intent: {r['has_create_intent']}, Type: {r['document_type']}")
