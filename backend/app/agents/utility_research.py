"""Research public utility data for a portfolio building; never invent actual bills."""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[3]


def load_property(building_id):
    with (ROOT / 'backend/data/portfolio.json').open(encoding='utf-8') as f:
        buildings = json.load(f)['buildings']
    for building in buildings:
        if str(building['building_id']) == str(building_id):
            return building
    raise ValueError(f'Unknown portfolio building: {building_id}')


def research(building_id):
    from deepagents import create_deep_agent
    from langchain_core.tools import tool
    from tavily import TavilyClient

    building = load_property(building_id)
    tavily = TavilyClient(api_key=os.environ['TAVILY_API_KEY'])

    @tool
    def search_public_sources(query: str) -> str:
        """Search public sources for official tariffs and building energy disclosures."""
        results = tavily.search(query=query, search_depth='advanced', max_results=5)
        return json.dumps([{'title': x.get('title'), 'url': x.get('url'),
                            'content': x.get('content')} for x in results.get('results', [])])

    @tool
    def lookup_electricity_tariffs(address: str) -> str:
        """Get OpenEI commercial electricity tariff candidates for an address."""
        key = os.environ.get('OPENEI_API_KEY')
        if not key:
            return json.dumps({'error': 'OPENEI_API_KEY not configured'})
        response = requests.get('https://api.openei.org/utility_rates', params={
            'version': 'latest', 'format': 'json', 'api_key': key,
            'address': address, 'sector': 'Commercial', 'limit': 25,
            'detail': 'full'}, timeout=25)
        response.raise_for_status()
        data = response.json()
        fields = ('name', 'utility', 'label', 'uri', 'startdate', 'enddate',
                  'fixedmonthlycharge', 'energyratestructure', 'demandratestructure')
        return json.dumps({'candidates': [{k: item.get(k) for k in fields}
                                           for item in data.get('items', [])],
                           'warning': 'Candidates only; verify eligibility and dates'})

    agent = create_deep_agent(
        model=os.getenv('UTILITY_RESEARCH_MODEL', 'openai:gpt-4.1'),
        tools=[search_public_sources, lookup_electricity_tariffs],
        system_prompt=(
            'Research US commercial utility tariffs and public energy disclosures. '
            'Prioritize primary sources and include URLs. Never invent actual bills, '
            'energy usage, rates, tariff eligibility, or service providers. '
            'Do not calculate energy costs or retrofit savings. '
            'Return only JSON with keys electricity, natural_gas, building_consumption, '
            'sources, notes. Use null for unknown numbers. Mark unverified rates as candidates.'
        ),
    )
    message = (f"Research building {building['building_id']}: {building['name']}, "
               f"{building['address']}, {building['property_type']}, "
               f"{building['rba_sqft']} square feet. Find applicable commercial "
               'electricity and natural gas tariffs and any public property-specific '
               'energy disclosures. Distinguish verified tariffs from candidates, '
               'and actual measured consumption from estimates. Cite source URLs.')
    response = agent.invoke({'messages': [{'role': 'user', 'content': message}]})
    answer = response['messages'][-1].content
    if not isinstance(answer, str):
        answer = json.dumps(answer)
    clean = answer.strip()
    if clean.startswith('```'):
        clean = clean.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
    try:
        data = json.loads(clean)
    except json.JSONDecodeError:
        data = {'raw_research': answer, 'parse_status': 'manual_review_required'}
    result = {'building_id': str(building_id), 'building_name': building['name'],
              'address': building['address'],
              'researched_at': datetime.now(timezone.utc).isoformat(),
              'measurement_status': 'research_only_not_actual_utility_bill',
              'research': data}
    path = ROOT / 'backend/data/utility_research' / f'{building_id}.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2), encoding='utf-8')
    return path


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--building-id', default='23551')
    args = parser.parse_args()
    print(research(args.building_id))
