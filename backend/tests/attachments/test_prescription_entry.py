from uuid import uuid4

import pytest
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.lib.units import mm
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.document_template import DocumentTemplate
from app.models.user import User
from app.services.document_templates import (
    PRESCRIPTION_CONTENT, PRESCRIPTION_TEMPLATE, RECALL_TEMPLATE_SIX_MONTHS,
    RECALL_TEMPLATE_TWELVE_MONTHS, ensure_default_templates,
)
from app.services.pdf_documents import _wrap_pdf_line


DETAILS = {
    "medicine": "Synthetic medicine - no clinical use",
    "directions": "Synthetic directions\nSecond line retained",
    "quantity": "Synthetic quantity",
    "prescriber_name": "Synthetic Prescriber",
    "prescriber_gdc": "TEST-ONLY",
}


def setup_case(client, headers, *, content=PRESCRIPTION_CONTENT, kind="prescription"):
    patient = client.post('/patients', headers=headers, json={
        'first_name': 'Prescription', 'last_name': 'Synthetic', 'date_of_birth': '1980-01-02',
    })
    assert patient.status_code == 201
    template = client.post('/document-templates', headers=headers, json={
        'name': 'Synthetic prescription '+uuid4().hex[:8], 'kind': kind, 'content': content,
    })
    assert template.status_code == 201
    return patient.json()['id'], template.json()['id']


def test_typed_prescription_preview_saved_snapshot_and_pdf(api_client, auth_headers):
    patient_id, template_id = setup_case(api_client, auth_headers)
    payload = {'template_id': template_id, 'prescription': DETAILS}
    path = f'/patients/{patient_id}/documents'
    preview = api_client.post(path+'/preview', headers=auth_headers, json=payload)
    assert preview.status_code == 200
    text = preview.json()['rendered_content']
    assert preview.json()['unknown_fields'] == []
    assert 'Prescription Synthetic' in text and '1980-01-02' in text
    assert all(value in text for value in DETAILS.values())
    assert "Prescriber's signature: ____" in text
    assert '{{' not in text
    headers = {**auth_headers, 'Request-Id': 'prescription-'+uuid4().hex}
    saved = api_client.post(path, headers=headers, json=payload)
    assert saved.status_code == 201
    document = saved.json()
    assert document['rendered_content'] == text
    repeated = api_client.post(path, headers=headers, json=payload)
    assert repeated.status_code == 201 and repeated.json()['id'] == document['id']
    changed = api_client.patch(f'/document-templates/{template_id}', headers=auth_headers,
                               json={'content': 'Changed template'})
    assert changed.status_code == 200
    result = api_client.get(f"/patient-documents/{document['id']}/download", headers=auth_headers)
    assert result.text == text
    pdf = api_client.get(f"/patient-documents/{document['id']}/download?format=pdf", headers=auth_headers)
    assert pdf.status_code == 200 and pdf.content.startswith(b'%PDF-')


@pytest.mark.parametrize('action', ['', '/preview'])
def test_missing_blank_or_misplaced_details_are_rejected(api_client, auth_headers, action):
    patient_id, template_id = setup_case(api_client, auth_headers)
    path = f'/patients/{patient_id}/documents'+action
    assert api_client.post(path, headers=auth_headers, json={'template_id': template_id}).status_code == 400
    for details in ({**DETAILS, 'medicine': '  '}, {**DETAILS, 'directions': 'x'*2001},
                    {**DETAILS, 'quantity': ''}, {**DETAILS, 'prescriber_name': '\x00unsafe'}):
        assert api_client.post(path, headers=auth_headers, json={
            'template_id': template_id, 'prescription': details,
        }).status_code == 422
    for kind, content in [('letter', 'Routine letter'), ('prescription', '{{prescription.medicine}}')]:
        _, other_id = setup_case(api_client, auth_headers, content=content, kind=kind)
        assert api_client.post(path, headers=auth_headers, json={
            'template_id': other_id, 'prescription': DETAILS,
        }).status_code == 400


def test_typed_text_is_not_evaluated_as_patient_fields(api_client, auth_headers):
    patient_id, template_id = setup_case(api_client, auth_headers)
    details = {**DETAILS, 'directions': 'Literal {{patient.full_name}} marker'}
    result = api_client.post(f'/patients/{patient_id}/documents/preview', headers=auth_headers,
                            json={'template_id': template_id, 'prescription': details})
    assert result.status_code == 200
    assert details['directions'] in result.json()['rendered_content']
    assert result.json()['unknown_fields'] == []


def test_default_templates_are_present_and_preserve_edits(api_client, auth_headers):
    templates = api_client.get('/document-templates', headers=auth_headers).json()
    for name in (PRESCRIPTION_TEMPLATE, RECALL_TEMPLATE_SIX_MONTHS, RECALL_TEMPLATE_TWELVE_MONTHS):
        assert sum(row['name'] == name for row in templates) == 1
    # Seeding must preserve edits to an existing default template.
    with SessionLocal() as db:
        actor = db.scalar(select(User).order_by(User.id))
        template = db.scalar(select(DocumentTemplate).where(DocumentTemplate.name == PRESCRIPTION_TEMPLATE))
        original = template.content
        try:
            template.content = 'Synthetic custom text'
            db.commit()
            assert ensure_default_templates(db, actor=actor) == 0
            db.refresh(template)
            assert template.content == 'Synthetic custom text'
        finally:
            template.content = original
            db.commit()


def test_pdf_wrap_keeps_long_words_inside_printable_width():
    text = 'W'*500
    lines = _wrap_pdf_line(text, 170*mm)
    assert ''.join(lines) == text
    assert all(stringWidth(line, 'Helvetica', 11) <= 170*mm for line in lines)
    assert _wrap_pdf_line('', 170*mm) == ['']
