import json
from pathlib import Path
from txori_kantua.storage import Store


def test_dashboard_queries_execute_against_schema(tmp_path):
    store=Store(tmp_path/'db')
    dashboard=json.loads((Path(__file__).parents[1]/'dashboards/txori.json').read_text())
    for panel in dashboard['panels']:
        query=panel['targets'][0]['queryText'].replace('$__from','0').replace('$__to','9999999999999')
        store.db.execute(query).fetchall()
    store.close()
