"""
WINDI ISP Endpoints v2.0 for A4 Desk BABEL
Institutional Style Profile API with Templates Support

Version: 2.0.0
Date: 03-Feb-2026
Author: WINDI Publishing House

New Endpoints:
- /api/isp/<profile_id>/tokens     - Design tokens
- /api/isp/<profile_id>/templates  - List available templates
- /api/isp/<profile_id>/template/<name> - Get specific template
- /api/isp/<profile_id>/forms      - List available forms
- /api/isp/<profile_id>/form/<name> - Get specific form
- /api/isp/<profile_id>/components - List available components
- /api/isp/<profile_id>/component/<name> - Get specific component
- /api/isp/<profile_id>/summary    - Full ISP summary
- /api/isp/<profile_id>/preview    - Preview rendered template
"""
import sys
sys.path.insert(0, '/opt/windi/isp')

from flask import Blueprint, jsonify, request, Response
from datetime import datetime

# Import ISP Loader v2.0 functions
from isp_loader import (
    list_profiles,
    load_profile,
    load_css,
    load_tokens,
    load_template,
    load_component,
    load_form,
    list_templates,
    list_forms,
    list_components,
    get_isp_summary,
    render_isp_template,
    build_full_document,
    generate_styled_html,
)

isp_bp = Blueprint('isp', __name__)


# ============================================================
# EXISTING ENDPOINTS (v1.0 - preserved for compatibility)
# ============================================================

@isp_bp.route('/api/isp/list')
def api_list_isp():
    """Lista todos os ISPs disponíveis"""
    profiles = list_profiles()
    return jsonify({"profiles": profiles})


@isp_bp.route('/api/isp/<profile_id>')
def api_get_isp(profile_id):
    """Retorna detalhes de um ISP (profile.json)"""
    profile = load_profile(profile_id)
    if not profile:
        return jsonify({"error": "Profile not found"}), 404
    return jsonify(profile)


@isp_bp.route('/api/isp/<profile_id>/css')
def api_get_isp_css(profile_id):
    """Retorna CSS de um ISP"""
    css = load_css(profile_id)
    if not css:
        return "", 404
    return Response(css, mimetype='text/css')


# ============================================================
# NEW ENDPOINTS v2.0 - Templates & Components
# ============================================================

@isp_bp.route('/api/isp/<profile_id>/tokens')
def api_get_tokens(profile_id):
    """
    Retorna design tokens de um ISP.

    Returns:
        JSON with colors, typography, spacing, borders, components
    """
    tokens = load_tokens(profile_id)
    if not tokens:
        return jsonify({"error": "Tokens not found", "profile_id": profile_id}), 404
    return jsonify(tokens)


@isp_bp.route('/api/isp/<profile_id>/templates')
def api_list_templates(profile_id):
    """
    Lista templates HTML disponíveis para um ISP.

    Returns:
        {"templates": ["letter", "form", "memo", ...]}
    """
    templates = list_templates(profile_id)
    return jsonify({
        "profile_id": profile_id,
        "templates": templates,
        "count": len(templates)
    })


@isp_bp.route('/api/isp/<profile_id>/template/<template_name>')
def api_get_template(profile_id, template_name):
    """
    Retorna HTML de um template específico.

    Args:
        profile_id: ID do ISP (ex: deutsche-bahn)
        template_name: Nome do template (ex: letter, form)

    Returns:
        HTML content ou 404
    """
    html = load_template(profile_id, template_name)
    if not html:
        return jsonify({
            "error": "Template not found",
            "profile_id": profile_id,
            "template_name": template_name,
            "available": list_templates(profile_id)
        }), 404
    return Response(html, mimetype='text/html')


@isp_bp.route('/api/isp/<profile_id>/forms')
def api_list_forms(profile_id):
    """
    Lista formulários institucionais disponíveis para um ISP.

    Returns:
        {"forms": ["transportauftrag", "urlaubsantrag", ...]}
    """
    forms = list_forms(profile_id)
    return jsonify({
        "profile_id": profile_id,
        "forms": forms,
        "count": len(forms)
    })


@isp_bp.route('/api/isp/<profile_id>/form/<form_name>')
def api_get_form(profile_id, form_name):
    """
    Retorna HTML de um formulário específico.

    Args:
        profile_id: ID do ISP
        form_name: Nome do formulário (ex: transportauftrag)

    Returns:
        HTML content ou 404
    """
    html = load_form(profile_id, form_name)
    if not html:
        return jsonify({
            "error": "Form not found",
            "profile_id": profile_id,
            "form_name": form_name,
            "available": list_forms(profile_id)
        }), 404
    return Response(html, mimetype='text/html')


@isp_bp.route('/api/isp/<profile_id>/components')
def api_list_components(profile_id):
    """
    Lista componentes reutilizáveis disponíveis para um ISP.

    Returns:
        {"components": ["header", "footer", "signature-block", ...]}
    """
    components = list_components(profile_id)
    return jsonify({
        "profile_id": profile_id,
        "components": components,
        "count": len(components)
    })


@isp_bp.route('/api/isp/<profile_id>/component/<component_name>')
def api_get_component(profile_id, component_name):
    """
    Retorna HTML de um componente específico.

    Args:
        profile_id: ID do ISP
        component_name: Nome do componente (ex: header, footer)

    Returns:
        HTML content ou string vazia
    """
    html = load_component(profile_id, component_name)
    if not html:
        return jsonify({
            "error": "Component not found",
            "profile_id": profile_id,
            "component_name": component_name,
            "available": list_components(profile_id)
        }), 404
    return Response(html, mimetype='text/html')


@isp_bp.route('/api/isp/<profile_id>/summary')
def api_get_summary(profile_id):
    """
    Retorna resumo completo de um ISP.

    Returns:
        JSON with profile info, templates, forms, components, etc.
    """
    summary = get_isp_summary(profile_id)
    if not summary.get("exists"):
        return jsonify({"error": "Profile not found", "profile_id": profile_id}), 404
    return jsonify(summary)


@isp_bp.route('/api/isp/<profile_id>/preview', methods=['POST'])
def api_preview_template(profile_id):
    """
    Renderiza preview de um template com dados fornecidos.

    Request Body:
        {
            "template_type": "letter" | "form" | "memo",
            "form_id": "transportauftrag" (optional),
            "content": "<p>Document content...</p>",
            "context": {
                "title": "My Document",
                "doc_date": "03.02.2026",
                ...
            }
        }

    Returns:
        Rendered HTML
    """
    data = request.get_json() or {}

    template_type = data.get("template_type", "letter")
    form_id = data.get("form_id")
    content = data.get("content", "")
    context = data.get("context", {})

    # Add default context values
    context.setdefault("title", "Preview Document")
    context.setdefault("doc_date", datetime.now().strftime("%d.%m.%Y"))
    context.setdefault("windi_level", "LOW")
    context.setdefault("windi_receipt", "PREVIEW-MODE")
    context.setdefault("show_windi", True)

    # Build full document
    html = build_full_document(
        profile_id,
        content,
        template_type=template_type,
        form_id=form_id,
        context=context
    )

    if not html:
        # Fallback to simple styled HTML
        html = generate_styled_html(
            profile_id,
            context.get("title", "Preview"),
            content,
            context.get("doc_date", "")
        )

    if not html:
        return jsonify({
            "error": "Could not render template",
            "profile_id": profile_id,
            "template_type": template_type,
            "form_id": form_id
        }), 400

    return Response(html, mimetype='text/html')


@isp_bp.route('/api/isp/<profile_id>/render-component', methods=['POST'])
def api_render_component(profile_id):
    """
    Renderiza um componente com contexto fornecido.

    Request Body:
        {
            "component": "header" | "footer",
            "context": {
                "doc_type": "Transportauftrag",
                "doc_number": "DB-001",
                ...
            }
        }

    Returns:
        Rendered HTML
    """
    data = request.get_json() or {}

    component_name = data.get("component", "header")
    context = data.get("context", {})

    component_html = load_component(profile_id, component_name)
    if not component_html:
        return jsonify({
            "error": "Component not found",
            "component": component_name,
            "available": list_components(profile_id)
        }), 404

    rendered = render_isp_template(profile_id, component_html, context)
    return Response(rendered, mimetype='text/html')


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def apply_isp_to_export(profile_id, title, content_html):
    """
    Aplica ISP ao HTML para exportação.
    (Legacy function - preserved for compatibility)
    """
    if not profile_id:
        return None

    date_str = datetime.now().strftime("%d.%m.%Y")
    return generate_styled_html(profile_id, title, content_html, date_str)


print("✓ ISP Endpoints v2.0 registered")
