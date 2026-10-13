from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.settings import settings
from app.db.session import SessionLocal
from app.models.note import Note
from app.models.patient import Patient
from app.models.patient_document import PatientDocument
from app.models.prescription_template import PrescriptionTemplate
from app.models.user import User
from app.services import recall_email
from app.services.document_templates import PRESCRIPTION_TEMPLATE, RECALL_TEMPLATE_SIX_MONTHS, RECALL_TEMPLATE_TWELVE_MONTHS
from app.services.prescription_defaults import ensure_prescription_defaults

DETAILS = dict(medicine="Synthetic medicine", directions="Synthetic directions", quantity="Synthetic quantity",
               prescriber_name="Synthetic Dentist", prescriber_gdc="TEST-ONLY")


def document(client, headers, name=RECALL_TEMPLATE_SIX_MONTHS, **patient_changes):
    response = client.post('/patients', headers=headers, json={
        'first_name': 'Synthetic', 'last_name': 'DocumentCopy', 'date_of_birth': '1980-01-01',
        'address_line1': '1 Synthetic Street', 'postcode': 'ZZ1 1ZZ',
        'email': 'synthetic-patient@example.com', **patient_changes,
    })
    assert response.status_code == 201, response.text
    patient_id = response.json()['id']
    templates = client.get('/document-templates', headers=headers).json()
    template = next(t for t in templates if t['name'] == name)
    response = client.post(f'/patients/{patient_id}/documents', headers=headers, json={
        'template_id': template['id'], **({'prescription': DETAILS} if name == PRESCRIPTION_TEMPLATE else {}),
    })
    assert response.status_code == 201, response.text
    return patient_id, response.json()


def prepare(client, headers, doc, method='print', request_id=None):
    return client.post(f"/patient-documents/{doc['id']}/copies", json={'method': method},
                       headers={**headers, 'Request-Id': request_id or str(uuid4())})


def notes(client, headers, patient_id):
    response = client.get(f'/patients/{patient_id}/notes', headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize('name', [PRESCRIPTION_TEMPLATE, RECALL_TEMPLATE_SIX_MONTHS, RECALL_TEMPLATE_TWELVE_MONTHS])
def test_print_records_one_note_and_immutable_pdf(api_client, auth_headers, name):
    patient_id, doc = document(api_client, auth_headers, name)
    original = api_client.get(f"/patient-documents/{doc['id']}/download?format=pdf", headers=auth_headers).content
    key = str(uuid4())
    prepared = prepare(api_client, auth_headers, doc, request_id=key)
    assert prepared.status_code == 201, prepared.text
    copy_id = prepared.json()['id']
    assert notes(api_client, auth_headers, patient_id) == []  # preparation/cancel is not printing
    assert prepare(api_client, auth_headers, doc, request_id=key).json()['id'] == copy_id
    url = f'/document-copies/{copy_id}'
    for _ in range(2):
        done = api_client.post(url+'/confirm-print', headers=auth_headers)
        assert done.status_code == 200, done.text
        assert done.json()['status'] == 'printed'
    records = notes(api_client, auth_headers, patient_id)
    assert len(records) == 1 and records[0]['note_type'] == 'clinical'
    note = records[0]
    assert note['document_copy_id'] == copy_id and name in note['body']
    if name == PRESCRIPTION_TEMPLATE:
        assert 'before handwritten signature' in note['body']
    assert api_client.patch(f"/notes/{note['id']}", headers=auth_headers, json={'body':'Changed'}).status_code == 409
    # Later patient changes and deleting the source cannot change the linked PDF.
    with SessionLocal() as db:
        patient = db.get(Patient, patient_id)
        patient.address_line1 = 'Changed address'
        patient.last_name = 'Changed'
        db.commit()
    assert api_client.get(f"/patient-documents/{doc['id']}/download?format=pdf", headers=auth_headers).content == original
    assert api_client.delete(f"/patient-documents/{doc['id']}", headers=auth_headers).status_code == 200
    pdf = api_client.get(url+'/pdf', headers=auth_headers)
    assert pdf.status_code == 200 and pdf.content == original
    assert pdf.headers['cache-control'] == 'no-store'
    assert len(notes(api_client, auth_headers, patient_id)) == 1


def test_concurrent_preparation_and_confirmation_are_idempotent(api_client, auth_headers):
    patient_id, doc = document(api_client, auth_headers)
    key = str(uuid4())
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: prepare(api_client, auth_headers, doc, request_id=key), range(2)))
    assert [r.status_code for r in results] == [201, 201]
    copy_id = results[0].json()['id']
    assert results[1].json()['id'] == copy_id
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: api_client.post(f'/document-copies/{copy_id}/confirm-print', headers=auth_headers), range(2)))
    assert [r.status_code for r in results] == [200, 200]
    assert len(notes(api_client, auth_headers, patient_id)) == 1


@pytest.mark.parametrize("missing", [{"postcode": None, "date_of_birth": None}, {"postcode": "   "}])
def test_missing_identity_and_legacy_prescriptions_cannot_be_issued(api_client, auth_headers, missing):
    _, doc = document(api_client, auth_headers, PRESCRIPTION_TEMPLATE, **missing)
    assert prepare(api_client, auth_headers, doc).status_code == 409
    with SessionLocal() as db:
        record = db.get(PatientDocument, doc['id'])
        record.frozen_pdf = None
        db.commit()
    assert prepare(api_client, auth_headers, doc).status_code == 409


def enable_email(monkeypatch):
    monkeypatch.setattr(settings, 'recall_email_enabled', True)
    monkeypatch.setattr(settings, 'smtp_host', 'synthetic.invalid')
    monkeypatch.setattr(settings, 'smtp_username', 'synthetic')
    monkeypatch.setattr(settings, 'smtp_password', 'synthetic-test')


def test_email_off_by_default_and_prescriptions_never_emailed(api_client, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, 'recall_email_enabled', False)
    patient_id, doc = document(api_client, auth_headers)
    assert prepare(api_client, auth_headers, doc, 'email').status_code == 409
    _, prescription = document(api_client, auth_headers, PRESCRIPTION_TEMPLATE)
    enable_email(monkeypatch)
    assert prepare(api_client, auth_headers, prescription, 'email').status_code == 400
    assert notes(api_client, auth_headers, patient_id) == []


@pytest.fixture
def email_api_client():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:
        yield client


def test_email_sends_exact_attachment_and_records_once(email_api_client, auth_headers, monkeypatch):
    api_client = email_api_client
    enable_email(monkeypatch)
    sent = []
    monkeypatch.setattr(recall_email, 'send_recall', lambda copy: sent.append((copy.recipient, copy.pdf_bytes)))
    patient_id, doc = document(api_client, auth_headers)
    prepared = prepare(api_client, auth_headers, doc, 'email')
    assert prepared.status_code == 201, prepared.text
    copy_id = prepared.json()['id']
    assert prepared.json()['sender'] == 'clinicforimplant@gmail.com'
    url = f'/document-copies/{copy_id}'
    assert api_client.post(url+'/confirm-print', headers=auth_headers).status_code == 409
    for _ in range(2):
        assert api_client.post(url+'/send-email', headers=auth_headers).status_code == 200
    assert len(sent) == 1 and sent[0][0] == 'synthetic-patient@example.com'
    assert sent[0][1] == api_client.get(url+'/pdf', headers=auth_headers).content
    records = notes(api_client, auth_headers, patient_id)
    assert len(records) == 1 and 'accepted by mail server' in records[0]['body']


def test_uncertain_email_never_creates_success_note_or_auto_retries(email_api_client, auth_headers, monkeypatch):
    api_client = email_api_client
    enable_email(monkeypatch)
    calls = []
    def fail(copy):
        calls.append(copy.id)
        raise TimeoutError('synthetic transport failure')
    monkeypatch.setattr(recall_email, 'send_recall', fail)
    patient_id, doc = document(api_client, auth_headers)
    copy_id = prepare(api_client, auth_headers, doc, 'email').json()['id']
    url = f'/document-copies/{copy_id}'
    assert api_client.post(url+'/send-email', headers=auth_headers).status_code == 502
    assert api_client.post(url+'/send-email', headers=auth_headers).status_code == 409
    assert api_client.get(url, headers=auth_headers).json()['status'] == 'uncertain'
    assert len(calls) == 1 and notes(api_client, auth_headers, patient_id) == []


def test_sender_or_recipient_change_requires_new_review(email_api_client, auth_headers, monkeypatch):
    api_client = email_api_client
    enable_email(monkeypatch)
    patient_id, doc = document(api_client, auth_headers)
    copy_id = prepare(api_client, auth_headers, doc, 'email').json()['id']
    with SessionLocal() as db:
        db.get(Patient, patient_id).email = 'changed@example.com'
        db.commit()
    assert api_client.post(f'/document-copies/{copy_id}/send-email', headers=auth_headers).status_code == 409


def test_presets_preserve_edits_and_require_patient_quantity(api_client, auth_headers):
    rows = api_client.get('/prescription-templates', headers=auth_headers).json()
    for strength in ('150', '300'):
        preset = next(r for r in rows if r['name'] == f'Clindamycin {strength} mg capsules')
        assert preset['quantity'] == '' and preset['directions'] == 'Take one capsule every six hours.'
    with SessionLocal() as db:
        actor = db.scalar(select(User).order_by(User.id))
        preset = db.scalar(select(PrescriptionTemplate).where(PrescriptionTemplate.stock_key == 'clindamycin-150'))
        original = preset.name
        try:
            preset.name = 'Synthetic renamed favourite'
            db.commit()
            ensure_prescription_defaults(db, actor=actor)
            db.refresh(preset)
            assert preset.name == 'Synthetic renamed favourite'
            assert len(list(db.scalars(select(PrescriptionTemplate).where(PrescriptionTemplate.stock_key.is_not(None))))) == 9
        finally:
            preset.name = original
            db.commit()


def test_copy_permissions_archived_patient_and_key_conflicts(api_client, auth_headers):
    from app.core.security import create_access_token
    from app.models.user import Role
    from app.services.users import create_user
    from app.services.capabilities import replace_user_capabilities
    patient_id, doc = document(api_client, auth_headers)
    key = str(uuid4())
    copy_id = prepare(api_client, auth_headers, doc, request_id=key).json()['id']
    _, other = document(api_client, auth_headers)
    assert prepare(api_client, auth_headers, other, request_id=key).status_code == 409
    with SessionLocal() as db:
        user = create_user(db, email=f'synthetic-copy-{uuid4().hex}@example.com', password='SyntheticPrescription123!',
                           full_name='Synthetic Reader', role=Role.dentist)
        user_id = user.id
        replace_user_capabilities(db, user_id, ['documents.download', 'notes.view'])
    token = create_access_token(subject=str(user_id), secret=settings.secret_key, alg=settings.jwt_alg,
                                expires_minutes=settings.access_token_expire_minutes)
    reader = {'Authorization': f'Bearer {token}'}
    assert prepare(api_client, reader, doc).status_code == 403
    assert api_client.get(f'/document-copies/{copy_id}/pdf', headers=reader).status_code == 200
    assert api_client.post(f'/document-copies/{copy_id}/confirm-print', headers=reader).status_code == 403
    assert api_client.get(f'/document-copies/{copy_id}/pdf').status_code == 401
    with SessionLocal() as db:
        replace_user_capabilities(db, user_id, ['notes.view'])
    assert api_client.get(f'/document-copies/{copy_id}/pdf', headers=reader).status_code == 403
    from datetime import datetime, timezone
    with SessionLocal() as db:
        db.get(Patient, patient_id).deleted_at = datetime.now(timezone.utc)
        db.commit()
    assert api_client.get(f'/document-copies/{copy_id}/pdf', headers=auth_headers).status_code == 404
    assert api_client.post(f'/document-copies/{copy_id}/confirm-print', headers=auth_headers).status_code == 404


def test_smtp_requires_tls_and_attaches_pdf(monkeypatch):
    from types import SimpleNamespace
    enable_email(monkeypatch)
    monkeypatch.setattr(settings, 'smtp_ssl', False)
    events = []
    messages = []
    class FakeSMTP:
        def __init__(self, *args, **kwargs): events.append('connect')
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def starttls(self, **kwargs): events.append('tls')
        def login(self, *args): events.append('login')
        def send_message(self, message):
            events.append('send')
            messages.append(message)
            return {}
    monkeypatch.setattr(recall_email.smtplib, 'SMTP', FakeSMTP)
    recall_email.send_recall(SimpleNamespace(id=123, sender='synthetic-practice@example.com',
                          recipient='synthetic-patient@example.com', pdf_bytes=b'%PDF-synthetic'))
    assert events == ['connect', 'tls', 'login', 'send']
    message = messages[0]
    assert message['To'] == 'synthetic-patient@example.com'
    assert list(message.iter_attachments())[0].get_payload(decode=True) == b'%PDF-synthetic'


@pytest.mark.parametrize('strength', ['250', '500'])
def test_liquid_presets_require_supply_and_preserve_full_patient_details(api_client, auth_headers, strength):
    rows = api_client.get('/prescription-templates', headers=auth_headers).json()
    liquid = next(r for r in rows if r['medicine'].startswith(f'Amoxicillin {strength} mg/5 mL oral suspension'))
    assert liquid['directions'] == 'Take 5 mL three times a day.'
    assert liquid['quantity'] == ''
    patient_id, initial = document(api_client, auth_headers, PRESCRIPTION_TEMPLATE,
                                  title='Ms', first_name='Synthetic Sarah', last_name='Example',
                                  address_line1='Flat 2', address_line2='12 Example Lane',
                                  city='Synthetic Town', postcode='ZZ1 1ZZ')
    prescription = {**DETAILS, **{key: liquid[key] for key in ('medicine', 'directions', 'quantity')}}
    path = f'/patients/{patient_id}/documents'
    payload = {'template_id': initial['template_id'], 'prescription': prescription}
    assert api_client.post(path, headers=auth_headers, json=payload).status_code == 422
    prescription['quantity'] = '100 mL'  # Synthetic test supply; never a default.
    saved = api_client.post(path, headers=auth_headers, json=payload)
    assert saved.status_code == 201, saved.text
    doc = saved.json()
    assert not doc['issue_blockers']
    for text in ('Ms Synthetic Sarah Example', 'Flat 2', '12 Example Lane', 'Synthetic Town',
                 'ZZ1 1ZZ', '1980-01-01', 'Age:', liquid['medicine'], liquid['directions'],
                 'Quantity: 100 mL', DETAILS['prescriber_name'], DETAILS['prescriber_gdc'], "Prescriber's signature"):
        assert text in doc['rendered_content']
    assert prepare(api_client, auth_headers, doc).status_code == 201
