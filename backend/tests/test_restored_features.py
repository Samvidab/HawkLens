"""Restored feature contracts; synthetic inputs exist only in temporary test data."""
import json
import pytest
from fastapi.testclient import TestClient
from app.config import get_settings
from app.main import app

@pytest.fixture
def restored(tmp_path,monkeypatch):
    monkeypatch.setenv('DATA_DIR',str(tmp_path/'data'));monkeypatch.setenv('CACHE_DIR',str(tmp_path/'cache'));get_settings.cache_clear()
    d=tmp_path/'data';b=d/'buildings/b1';b.mkdir(parents=True)
    (b/'profile.json').write_text(json.dumps({'building_id':'b1','name':'Test fixture','rba_sqft':1000,'source_fields':{'rba_sqft':'test fixture only'}}))
    yield TestClient(app),d,tmp_path/'cache'
    get_settings.cache_clear()

def test_history_never_replaces_current_plan(restored):
    c,d,_=restored;(d/'plans').mkdir();(d/'memo').mkdir()
    (d/'plans/current.json').write_text('{"plan_id":"p2"}');(d/'plans/p1.json').write_text('{"plan_id":"p1"}');(d/'memo/p1.md').write_text('# Saved fixture')
    (d/'runs/research_only').mkdir(parents=True);(d/'runs/research_only/events.jsonl').write_text('')
    before=(d/'plans/current.json').read_bytes()
    assert c.get('/history').json()['current_plan_id']=='p2'
    assert any(r['run_id']=='research_only' and r['events_available'] for r in c.get('/history').json()['runs'])
    assert c.get('/history/plans/p1').json()['memo_markdown']=='# Saved fixture'
    assert (d/'plans/current.json').read_bytes()==before
    assert c.get('/history/plans/missing').status_code==404

def test_original_thumbnail_and_missing_state(restored):
    c,d,cache=restored;p=cache/'media/mp/model1';p.mkdir(parents=True);(p/'thumb.jpg').write_bytes(b'original bytes')
    assert c.get('/properties/model1/thumbnail').content==b'original bytes'
    assert c.get('/properties/missing/thumbnail').status_code==404

def test_explicit_energy_inputs_use_recorded_area(restored):
    c,_,_=restored;assert c.post('/analysis/energy',json={'building_id':'b1'}).status_code==422
    values={'building_id':'b1','annual_kwh_per_sqft':10,'electricity_usd_per_kwh':.1,'annual_therms_per_sqft':0,'gas_usd_per_therm':0}
    data=c.post('/analysis/energy',json=values).json();assert data['annual_spend_estimate_usd']==1000
    assert data['measurement_status']=='estimate_not_actual_utility_bill'
    assert data['building_profile_source_fields']['rba_sqft']=='test fixture only'
    values['electricity_usd_per_kwh']=-1;assert c.post('/analysis/energy',json=values).status_code==422

def test_bill_validation_rejects_duplicates_and_labels_input(restored):
    c,_,_=restored;row='b1,2026-01-01,2026-01-31,electricity,12.50\n';header='building_id,service_start,service_end,utility,amount_usd\n'
    data=c.post('/analysis/bills',json={'building_id':'b1','csv_text':header+row}).json()
    assert data['observed_spend_usd']==12.5 and data['annualized'] is False
    assert data['measurement_status']=='user_provided_bill_records_not_independently_verified'
    assert c.post('/analysis/bills',json={'building_id':'b1','csv_text':header+row+row}).status_code==422

def test_stale_memo_guard_and_pdf_without_finance(restored):
    c,d,_=restored;(d/'plans').mkdir();(d/'memo').mkdir()
    (d/'plans/current.json').write_text(json.dumps({'plan_id':'p1','selected':['u1'],'total_upfront':120,'exp_npv':-10}))
    (d/'memo/p1.md').write_text('# Memo\n\n## Inputs\n\nRecorded fixture only.\n\n| Type | Cost |\n|---|---|\n| Fixture | $120 |')
    assert c.post('/documents/memo/generate',json={'plan_id':'stale'}).status_code==409
    assert c.get('/documents/memo/download?plan_id=stale').status_code==409
    response=c.get('/documents/memo/download?plan_id=p1');assert response.status_code==200 and response.content.startswith(b'%PDF-')
    assert 'attachment' in response.headers['content-disposition'];assert not (d/'finance').exists()

def test_missing_research_stays_null(restored):
    c,_,_=restored;result=c.get('/research/b1').json()
    assert result['utility_research'] is None and result['energy_estimate'] is None
    assert c.get('/research/missing').status_code==404


def test_dedicated_nessie_mapping_reuses_read_client_without_fabricating_fields(monkeypatch):
    from app.integrations import nessie_client as nes
    monkeypatch.setattr(nes, "env_value", lambda key: "recorded-account-fixture" if key == "NESSIE_BUILDING_ACCOUNT_B1" else None)
    calls=[]
    def read(method,path):
        calls.append((method,path))
        return [{"_id":"fixture-bill","payment_date":"2026-01-31","payment_amount":12.5},
                {"_id":"missing-amount","payment_date":"2026-01-31"}]
    monkeypatch.setattr(nes,"_call",read)
    result=nes._live_get_bills("b1")
    assert calls==[("get","/accounts/recorded-account-fixture/bills")]
    assert len(result)==1 and result[0].amount_usd==12.5 and result[0].kwh is None and result[0].utility is None
