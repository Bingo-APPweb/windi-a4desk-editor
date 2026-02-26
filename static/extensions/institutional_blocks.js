/**
 * WINDI A4Desk BABEL v4.7 - Institutional Blocks
 * KI verarbeitet. Mensch entscheidet. WINDI garantiert.
 */

const INSTITUTIONAL_BLOCKS = {
  german_gov_v1: {
    templateName: "German Government Letter",
    standard: "DIN 5008",
    blocks: [
      { id: "betreff", label: "Betreff", labelEN: "Subject", required: true, maxInstances: 1, placeholder: "Betreff eingeben...", template: "<strong>Betreff:</strong> " },
      { id: "bezug", label: "Bezug", labelEN: "Reference", required: false, maxInstances: 1, placeholder: "Ihr Schreiben vom...", template: "<strong>Bezug:</strong> " },
      { id: "anrede", label: "Anrede", labelEN: "Salutation", required: true, maxInstances: 1, placeholder: "Sehr geehrte Damen und Herren,", template: "" },
      { id: "haupttext", label: "Haupttext", labelEN: "Main Text", required: true, maxInstances: null, placeholder: "Text eingeben...", template: "" },
      { id: "massnahmen", label: "Massnahmen", labelEN: "Measures", required: false, maxInstances: 1, placeholder: "Erforderliche Massnahmen...", template: "<strong>Massnahmen:</strong><br>" },
      { id: "anlagen", label: "Anlagen", labelEN: "Attachments", required: false, maxInstances: 1, placeholder: "- Anlage 1", template: "<strong>Anlagen:</strong><br>" },
      { id: "grussformel", label: "Grussformel", labelEN: "Closing", required: true, maxInstances: 1, placeholder: "Mit freundlichen Gruessen", template: "" }
    ]
  },
  eu_official_v1: {
    templateName: "EU Official Document",
    standard: "EU Format",
    blocks: [
      { id: "executive_summary", label: "Executive Summary", labelDE: "Zusammenfassung", required: true, maxInstances: 1, placeholder: "Brief overview...", template: "<strong>Executive Summary</strong><br>" },
      { id: "risk_assessment", label: "Risk Assessment", labelDE: "Risikobewertung", required: true, maxInstances: 1, placeholder: "Identified risks...", template: "<strong>Risk Assessment</strong><br>" },
      { id: "compliance_measures", label: "Compliance Measures", labelDE: "Konformitaetsmassnahmen", required: true, maxInstances: 1, placeholder: "Implemented measures...", template: "<strong>Compliance Measures</strong><br>" },
      { id: "recommendations", label: "Recommendations", labelDE: "Empfehlungen", required: false, maxInstances: 1, placeholder: "Suggested improvements...", template: "<strong>Recommendations</strong><br>" }
    ]
  },
  windi_formal_v1: {
    templateName: "WINDI Formal Document",
    standard: "WINDI SYSTEM",
    blocks: [
      { id: "memo_header", label: "Memo Header", labelDE: "Memo-Kopf", required: true, maxInstances: 1, placeholder: "", template: "<strong>MEMORANDUM</strong><br><br>To: <br>From: <br>Date: <br>Re: " },
      { id: "memo_body", label: "Body", labelDE: "Inhalt", required: true, maxInstances: null, placeholder: "Content...", template: "" },
      { id: "action_items", label: "Action Items", labelDE: "Massnahmen", required: false, maxInstances: 1, placeholder: "- Action 1", template: "<strong>Action Items:</strong><br>" }
    ]
  }
};

function getBlocksForTemplate(templateId) {
  const tpl = INSTITUTIONAL_BLOCKS[templateId];
  return tpl ? tpl.blocks : [];
}

function getRequiredBlocks(templateId) {
  return getBlocksForTemplate(templateId).filter(b => b.required);
}

function canInsertBlock(templateId, blockId, currentCount) {
  const blocks = getBlocksForTemplate(templateId);
  const block = blocks.find(b => b.id === blockId);
  if (!block) return false;
  if (block.maxInstances === null) return true;
  return currentCount < block.maxInstances;
}

function countBlocksInEditor(blockId) {
  const editor = document.getElementById('editor');
  return editor.querySelectorAll('[data-block-type="' + blockId + '"]').length;
}

function insertInstitutionalBlock(templateId, blockId) {
  const blocks = getBlocksForTemplate(templateId);
  const block = blocks.find(b => b.id === blockId);
  if (!block) return false;
  
  const count = countBlocksInEditor(blockId);
  if (!canInsertBlock(templateId, blockId, count)) {
    window.toast ? toast('Maximum ' + block.label + ' reached', 'warning') : alert('Maximum reached');
    return false;
  }
  
  const html = '<div class="institutional-block" data-block-type="' + block.id + '" data-block-origin="human" data-block-timestamp="' + new Date().toISOString() + '" data-required="' + block.required + '"><div class="block-label">' + block.label + '</div><div class="block-content">' + block.template + block.placeholder + '</div></div><p><br></p>';
  
  const editor = document.getElementById('editor');
  const body = editor.querySelector('.body');
  if (body) { body.innerHTML += html; } else { editor.innerHTML += html; }
  
  if (window.WINDI_TOOLBAR) window.WINDI_TOOLBAR.updateComplianceIndicator();
  return true;
}

function validateDocumentStructure(templateId) {
  const required = getRequiredBlocks(templateId);
  const missing = [];
  required.forEach(block => { if (countBlocksInEditor(block.id) === 0) missing.push(block); });
  return { valid: missing.length === 0, missing: missing };
}

window.WINDI_BLOCKS = { INSTITUTIONAL_BLOCKS, getBlocksForTemplate, getRequiredBlocks, canInsertBlock, insertInstitutionalBlock, validateDocumentStructure, countBlocksInEditor };
console.log('[WINDI] Institutional Blocks v4.7 loaded');


