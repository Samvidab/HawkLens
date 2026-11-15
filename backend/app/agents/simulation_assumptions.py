from app.config import get_settings

"""HawkLens Houston assumption research. Run: python -m backend.app.agents.simulation_assumptions"""
import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from tavily import TavilyClient
from google import genai
from google.genai import types
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from deepagents import create_deep_agent

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / '.env')
load_dotenv()
OUT = get_settings().data_dir / 'simulation_assumptions'
UPGRADES = ['rooftop solar', 'cool roof', 'windows', 'insulation', 'heat pump', 'LED']
ITEMS = [
    ('1', 'Houston commercial electricity price (12-month average)', '$/kWh'),
    ('2', 'Houston commercial solar export buyback', '$/kWh'),
    ('3', 'ERCOT eGRID CO2 OUTPUT factor', 'kg CO2/kWh'),
    ('4', 'Houston PVWatts annual output', 'kWh/kW/year'),
    ('5a', 'Office electricity use intensity', 'kWh/ft2/year'),
    ('5b', 'Retail electricity use intensity', 'kWh/ft2/year'),
    ('5c', 'Industrial electricity use intensity', 'kWh/ft2/year'),
    ('5d', 'Multifamily electricity use intensity', 'kWh/ft2/year'),
    ('5e', 'All commercial buildings electricity use intensity', 'kWh/ft2/year'),
]
for u in UPGRADES:
    ITEMS.append((f'6 {u}', f'{u.title()} installed cost', '$/kW' if u == 'rooftop solar' else '$/ft2'))
for u in ['cool roof', 'windows', 'heat pump']:
    ITEMS.append((f'7 {u}', f'{u.title()} like-for-like replacement cost', '$/ft2'))
for u in UPGRADES:
    unit = ('kWh/kW/year (production)' if u == 'rooftop solar' else
            'kWh/ft2 roof-or-wall/year' if u in ('cool roof', 'insulation') else
            'fraction of whole-building electricity')
    ITEMS.append((f'8 {u}', f'{u.title()} annual electricity effect', unit))
for u in UPGRADES:
    ITEMS.append((f'9 {u}', f'{u.title()} lifespan', 'years'))
for u in UPGRADES:
    ITEMS.append((f'10 {u}', f'{u.title()} annual maintenance', '% of installed cost/year or none'))
for u in UPGRADES:
    ITEMS.append((f'11 {u}', f'{u.title()} incentive and probability', '% or $; probability 0-1'))
ITEMS.extend([
    ('12', 'Annual electricity price growth', '%/year'),
    ('13', 'Commercial real-estate discount rate', '%/year'),
    ('14', 'Inflation', '%/year'),
    ('15', 'Carbon fee probability, start year, price', 'probability 0-1; year; $/tonne CO2'),
    ('16', 'Probability new solar project placed in service by Dec 31 2027', 'probability 0-1'),
    ('17', 'Solar realized performance versus modeled output', 'fraction of modeled output delivered'),
])
PRIORITY = {'1', '3', '4', '5a', '5b', '5c', '5d', '5e', '6 LED', '6 heat pump',
            '8 LED', '8 heat pump', '11 rooftop solar', '11 heat pump', '16'}
IRS_179D = 'https://www.irs.gov/newsroom/faqs-for-modification-of-sections-25c-25d-25e-30c-30d-45l-45w-and-179d-under-public-law-119-21-139-stat-72-july-4-2025-commonly-known-as-the-one-big-beautiful-bill-obbb'
IRS_SOLAR = 'https://www.irs.gov/irb/2025-36_IRB'
EIA_TABLE = 'https://www.eia.gov/electricity/monthly/epm_table_grapher.php?t=epmt_5_6_a'


def assumptions_file():
    for p in (ROOT / 'ASSUMPTIONS.md', ROOT / 'backend' / 'ASSUMPTIONS.md', ROOT / 'docs' / 'ASSUMPTIONS.md'):
        if p.exists():
            return str(p.relative_to(ROOT)), p.read_text(encoding='utf-8')[:25000]
    return None, None


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return '\n'.join(str(p.get('text', '')) for p in content if isinstance(p, dict) and p.get('type') == 'text')
    return str(content)


def parse_json(content):
    raw = text_of(content).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        for match in re.finditer(r'\{', raw):
            try:
                obj, _ = decoder.raw_decode(raw[match.start():])
                if isinstance(obj, dict) and isinstance(obj.get('rows'), list):
                    return obj
            except json.JSONDecodeError:
                pass
    raise ValueError('Model response contained no valid JSON rows. Nothing was overwritten.')


def valid_url(value):
    if not isinstance(value, str) or any(c.isspace() for c in value):
        return False
    p = urlparse(value)
    return p.scheme == 'https' and bool(p.netloc) and '.' in p.netloc


def number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def make_prompt(group, assumptions_name, assumptions_text):
    catalog = '\n'.join(f'{i} | {name} | {unit}' for i, name, unit in group)
    prompt = f'''Research Houston commercial-building simulation inputs AS OF 2026-11-14.
Research ALL of these rows; return JSON ONLY: {{"rows":[{{"id":"...","typical":null,"low":null,"high":null,"source_url":null,"source_detail":null,"notes":"...","status":"missing","evidence_type":"unknown","monthly_observations":null,"incentive":null}}]}}.
Each source_url must be ONE exact publicly accessible page URL; source_detail must identify its specific table, date, scenario settings or formula. For sourced numbers, quote the exact supporting figure in notes. Do not invent a source or value. Use null if unverified. Use status sourced / estimated / missing / placeholder; evidence_type published_data / derived_calculation / analyst_assumption / unknown. When a published reference provides a different denominator, do not silently convert. Distinguish published values from scenario estimates.
Rows:
{catalog}

RESEARCH RULES:
1: Find the most recent 12 COMPLETE months in EIA Electric Power Monthly Table 5.6.A, TEXAS COMMERCIAL. Return monthly_observations as exactly 12 objects {{"month":"YYYY-MM","cents_per_kwh":NUMBER}} in chronological order. This is statewide utility revenue / sales proxy, not a Houston customer-specific billed tariff. Cite the exact EIA table. Never use a single month as a 12-month average.
2: Commercial export price needs a specific Houston/CenterPoint commercial plan and eligibility. Residential-only offers are NOT valid. Otherwise null.
3: EPA eGRID ERCT CO2 OUTPUT in lb/MWh multiplied by 0.00045359237 to kg/kWh; report data year. CO2, not CO2e.
4: PVWatts Houston actual run only; give size, tilt, azimuth, losses, DC/AC ratio and output. Otherwise null.
5a/5b: Prefer South Census region CBECS electricity-only EUI, compare national. 5c industrial is NOT automatically CBECS warehouse. 5d multifamily is NOT standard CBECS. 5e all-building weighted electricity-only average, NOT mean of category medians. Distinguish total site kBtu from electricity kWh.
6: Installed cost denominator: solar $/kW (multiply published $/W by 1000), windows $/ft2 window area, cool roof $/ft2 roof, insulation $/ft2 treated wall/roof, heat pump $/ft2 conditioned floor, LED $/ft2 floor.
7: Like-for-like replacements: candidate windows $30/ft2 window, heat pump $15/ft2 conditioned floor, cool roof $2.25/ft2 roof. Find actual replacement sources; don't present candidates as published data. replacement_due_now null absent site survey; replacement_credit_applied_typical ZERO unless asset due now.
8: Cool roof candidate 1.5 kWh/ft2 ROOF/year: seek Houston LBNL/ORNL. Insulation candidate 2.0 kWh/ft2 WALL/year: seek PNNL hot-humid. Windows 0.08, LED 0.12 must be share of WHOLE BUILDING ELECTRICITY saved, not HVAC or lighting alone. Heat pump 0.18 may include displaced GAS; the previous 0.10 is a provisional whole-building ELECTRICITY-only scenario, not a published finding. Electrification may increase electricity use. Solar production is NOT savings.
9 and 10: All six upgrade lifespan and annual O&M % of installed cost; identify specific product/measure, year and published table. If only annual $ or operating hours provided, explain the calculation.
11: For EACH upgrade, give structured incentive: program_name, type, payment_timing, amount_typical, amount_low, amount_high, amount_unit, probability_typical, probability_low, probability_high, eligibility, available_for_new_project, source_url, source_detail. Distinguish $/ft2 from % installed cost; no arbitrary 0.5. Research CenterPoint 2026 Commercial Standard Offer and federal tax rules. Section 179D not available if construction begins after June 30 2026. Ordinary rooftop air-source heat pumps do not automatically qualify for geothermal section 48 ITC. CenterPoint performance incentives may be $/kW verified demand and $/kWh verified savings; don't turn these into $/ft2 without load/savings. Probability of owner award null without evidence.
12-15: Distinguish published trend from scenarios. Discount 7.5% is analyst scenario. Carbon fee 15% chance, 2030 start, $50/tonne are analyst judgments (not sourced forecasts). Inflation 2.5% is a scenario.
16: Probability a NEW project begun Nov 2026 is INSTALLED, COMMISSIONED and placed in service by Dec 31 2027; this is NOT wage-rule compliance probability. IRS Notice 2025-42 distinguishes construction begun after July 4 2026 versus before. Without project schedule, probability null.
17: Realized solar output / PVWatts modeled output factor; proposed 0.90–0.97 is not verified until sourced. Avoid double-counting PVWatts default losses.
Do not assert that an incentive remains open in Nov 2026 without current program confirmation. Return every row even when missing.
'''
    if assumptions_text:
        prompt += f'\nASSUMPTIONS.md ({assumptions_name}); preserve its units exactly if they differ from catalog:\n{assumptions_text}\n'
    else:
        prompt += '\nASSUMPTIONS.md was not found; explicitly flag that exact model units could not be checked.\n'
    return prompt


def normalize(group, returned, checked):
    found = {str(x.get('id')): x for x in returned if isinstance(x, dict)}
    rows = []
    for ident, name, unit in group:
        f = found.get(ident, {})
        row = {
            'id': ident,
            'item': name,
            'typical': number(f.get('typical')),
            'low': number(f.get('low')),
            'high': number(f.get('high')),
            'unit': unit,
            'source_url': f.get('source_url') if valid_url(f.get('source_url')) else None,
            'source_detail': f.get('source_detail'),
            'checked_at': checked,
            'notes': str(f.get('notes') or ''),
            'status': f.get('status', 'missing'),
            'evidence_type': f.get('evidence_type', 'unknown'),
            'priority': ident in PRIORITY,
        }
        if ident == '1':
            row['monthly_observations'] = None
        if ident.startswith('7 '):
            row['replacement_due_now'] = None
            row['replacement_credit_applied_typical'] = 0
        if ident.startswith('11 '):
            row['incentive'] = None
        if row['status'] == 'sourced' and not row['source_url']:
            row['status'] = 'estimated'
            row['notes'] += ' Missing valid source URL.'
        if row['status'] == 'sourced' and not row['source_detail']:
            row['status'] = 'estimated'
            row['notes'] += ' Exact table/page/setting not provided.'
        if row['evidence_type'] == 'analyst_assumption' and row['status'] == 'sourced':
            row['status'] = 'estimated'
        if ident == '1':
            obs = f.get('monthly_observations')
            try:
                assert isinstance(obs, list) and len(obs) == 12
                months = [o['month'] for o in obs]
                assert len(set(months)) == 12 and months == sorted(months)
                assert all(re.fullmatch(r'20\d\d-(0[1-9]|1[0-2])', m) for m in months)
                vals = [float(o['cents_per_kwh']) for o in obs]
                assert all(0 < v < 100 for v in vals)
                row['monthly_observations'] = obs
                row['typical'] = round(sum(vals) / 1200, 6)
                row['low'] = round(min(vals) / 100, 6)
                row['high'] = round(max(vals) / 100, 6)
                row['notes'] += ' Computed arithmetic mean from 12 monthly observations; low/high are monthly extrema, not confidence intervals.'
                row['evidence_type'] = 'derived_calculation'
            except (AssertionError, TypeError, ValueError, KeyError):
                row.update(typical=None, low=None, high=None, status='missing')
                row['notes'] += ' Twelve dated monthly observations not provided.'
            if not row['source_url'] or not row['source_detail']:
                row.update(typical=None, low=None, high=None, status='missing')
        if ident == '6 rooftop solar' and row['typical'] is not None and 0 < row['typical'] < 100:
            for key in ('typical', 'low', 'high'):
                if row[key] is not None:
                    row[key] *= 1000
            row['notes'] += ' Converted $/W to $/kW (x1000).'
        if ident.startswith('7 '):
            row['replacement_due_now'] = None
            row['replacement_credit_applied_typical'] = 0
            row['notes'] += ' Like-for-like credit defaults to zero unless building assessment confirms replacement is due now.'
        if ident.startswith('11 '):
            f_inc = f.get('incentive') if isinstance(f.get('incentive'), dict) else {}
            keys = ('program_name', 'type', 'payment_timing', 'amount_typical', 'amount_low',
                    'amount_high', 'amount_unit', 'probability_typical', 'probability_low',
                    'probability_high', 'eligibility', 'available_for_new_project',
                    'source_url', 'source_detail')
            row['incentive'] = {k: f_inc.get(k) for k in keys}
            if ident != '11 rooftop solar':
                row['notes'] += ' Section 179D is unavailable for construction beginning after June 30, 2026.'
            if ident == '11 heat pump':
                row['notes'] += ' Air-source heat pumps do not automatically qualify for geothermal ITC.'
            if not row['incentive']['program_name'] or not row['incentive']['amount_unit']:
                row.update(typical=None, low=None, high=None, status='missing')
            # Do not treat any model-estimated owner probability as verified.
            for k in ('probability_typical', 'probability_low', 'probability_high'):
                row['incentive'][k] = None
            # Incentive amounts need their own unit and cannot safely fit a mixed scalar row.
            row['typical'] = row['low'] = row['high'] = None
            row['notes'] += ' Use incentive.amount_* with incentive.amount_unit; do not infer a single mixed-unit value.'
        if ident == '8 heat pump':
            row.update(typical=0.10, low=None, high=None,
                       status='estimated', evidence_type='analyst_assumption')
            row['notes'] += ' Provisional electricity-only savings scenario, not measured; gas-to-electric conversions require separate fuel accounting.'
        if ident == '13':
            row.update(typical=7.5, low=6.0, high=10.0, status='estimated', evidence_type='analyst_assumption', source_url=None)
            row['notes'] += ' Requested 7.5% scenario; low/high are sensitivity assumptions.'
        if ident == '14':
            row.update(typical=2.5, status='estimated', evidence_type='analyst_assumption', source_url=None)
            row['notes'] += ' 2.5% scenario, not a current measured inflation rate.'
        if ident == '15':
            row.update(typical=0.15, low=None, high=None, status='estimated', evidence_type='analyst_assumption', source_url=None)
            row['carbon_start_year_typical'] = 2030
            row['carbon_price_usd_per_tonne_typical'] = 50
            row['notes'] += ' 15% chance, 2030 start, $50/tonne are explicit analyst judgments.'
        if ident == '16':
            row.update(typical=None, low=None, high=None, status='missing', evidence_type='unknown',
                       source_url=IRS_SOLAR, source_detail='IRS Notice 2025-42, section 2.02')
            row['notes'] += ' Deadline documented, but project-specific completion probability is not established. Prior 95% wage compliance probability is invalid.'
        if ident == '2' and 'commercial' not in row['notes'].lower():
            row.update(typical=None, low=None, high=None, status='missing')
            row['notes'] += ' Commercial eligibility not confirmed.'
        if all(row[k] is None for k in ('typical', 'low', 'high')) and not ident.startswith('11 '):
            row['status'] = 'missing' if row['status'] != 'placeholder' else 'placeholder'
        rows.append(row)
    return rows


def research():
    if not os.getenv('VERTEX_API_KEY') or not os.getenv('TAVILY_API_KEY'):
        raise RuntimeError('Set VERTEX_API_KEY and TAVILY_API_KEY in .env')
    tavily = TavilyClient(api_key=os.environ['TAVILY_API_KEY'])

    @tool
    def search_public_sources(query: str) -> str:
        """Search published public sources; return title, URL and excerpts."""
        try:
            result = tavily.search(query=query, search_depth='advanced', max_results=5)
            return json.dumps([{'title': r.get('title'), 'url': r.get('url'),
                                'content': str(r.get('content', ''))[:4000]}
                               for r in result.get('results', [])])
        except Exception as exc:
            return json.dumps({'error': str(exc)})

    client = genai.Client(vertexai=True, api_key=os.environ['VERTEX_API_KEY'],
                          http_options=types.HttpOptions(api_version='v1'))
    model = ChatGoogleGenerativeAI(model='gemini-3.5-flash-lite', vertexai=True,
                                   google_api_key=os.environ['VERTEX_API_KEY'])
    model.client = client
    agent = create_deep_agent(model=model, tools=[search_public_sources], system_prompt=(
        'You are a rigorous energy-retrofit source researcher. Use the search tool. '
        'Return only valid JSON with rows array. Every published numerical claim must '
        'have an exact supporting source URL and source_detail. Never invent sources, '
        'tariff eligibility, incentive award probabilities or simulation outputs. '
        'Unknown inputs are null. Avoid conflating electricity and total site energy.'))
    assumptions_name, assumptions_text = assumptions_file()
    print('ASSUMPTIONS.md:', assumptions_name or 'not found', flush=True)
    checked = datetime.now(timezone.utc).date().isoformat()
    # Smaller batches reduce output truncation and make failures visible.
    batches = [ITEMS[i:i + 8] for i in range(0, len(ITEMS), 8)]
    all_rows = []
    for i, batch in enumerate(batches, 1):
        print(f'Researching batch {i}/{len(batches)}: {batch[0][0]} through {batch[-1][0]}', flush=True)
        prompt = make_prompt(batch, assumptions_name, assumptions_text)
        try:
            answer = agent.invoke({'messages': [{'role': 'user', 'content': prompt}]},
                                  config={'recursion_limit': 65})
            parsed = parse_json(answer['messages'][-1].content)
            all_rows.extend(normalize(batch, parsed['rows'], checked))
        except Exception as exc:
            print(f'Batch {i} failed: {exc}', flush=True)
            all_rows.extend(normalize(batch, [], checked))
    OUT.mkdir(parents=True, exist_ok=True)
    result = {'location': 'Houston, Texas, USA',
              'researched_at': datetime.now(timezone.utc).isoformat(),
              'assumptions_file': assumptions_name,
              'rows': all_rows,
              'warning': 'AI-assisted research is not independently audited. Missing and scenario values must be verified before financial use. Incentive probabilities are not automatically assumed.'}
    json_path = OUT / 'houston.json'
    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    md = ['# Houston simulation assumptions', '',
          '| Item | Typical / low / high | Unit | Source | Specific reference / notes |',
          '|---|---|---|---|---|']
    for r in all_rows:
        vals = f"{r['typical']} / {r['low']} / {r['high']}"
        if r.get('incentive'):
            inc = r['incentive']
            vals = f"{inc.get('amount_typical')} / {inc.get('amount_low')} / {inc.get('amount_high')} ({inc.get('amount_unit')})"
        source = r['source_url'] or 'Unverified'
        details = f"[{r['status']}; {r['evidence_type']}] {r.get('source_detail') or ''}; {r['notes']}"
        details = details.replace('|', '\\|').replace('\n', ' ')
        md.append(f"| {r['id']} {r['item']} | {vals} | {r['unit']} | {source} | {details} |")
    md_path = OUT / 'houston.md'
    md_path.write_text('\n'.join(md) + '\n', encoding='utf-8')
    print(f'Saved JSON: {json_path}\nSaved table: {md_path}', flush=True)
    print('Missing rows:', ', '.join(r['id'] for r in all_rows if r['status'] == 'missing'), flush=True)
    return json_path, md_path


if __name__ == '__main__':
    argparse.ArgumentParser().parse_args()
    research()
