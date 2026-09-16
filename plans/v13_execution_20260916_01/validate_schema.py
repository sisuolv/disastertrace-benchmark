"""Use existing system jsonschema, without installing into the project venv."""

import importlib.metadata
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from disastertrace.monitoring_v1.selector_contract_v2 import contract, parse_query_only


def main():
    output=Path(__file__).resolve().parent/'SELECTOR_SCHEMA_VALIDATION.json'
    rows=[]
    for handles in ([],['q0'],['q0','q1'],[f'q{i}' for i in range(1000)]):
        spec=contract(handles);Draft202012Validator.check_schema(spec['logical_schema'])
        provider=spec['provider_schema']['json_schema']['schema'];Draft202012Validator.check_schema(provider)
        validator=Draft202012Validator(provider)
        valid=[{'query_order':[]},{'query_order':handles[::-1]}]
        invalid=[{'query_order':['unregistered']},{'query_order':True},{'query_order':[], 'extra':1}]
        if handles:invalid.append({'query_order':[handles[0],handles[0]]})
        for value in valid:
            validator.validate(value);assert parse_query_only(json.dumps(value),handles)==value
        for value in invalid:
            assert list(validator.iter_errors(value))
            try:parse_query_only(json.dumps(value),handles)
            except ValueError:pass
            else:raise AssertionError('Parser accepted schema-invalid output')
        rows.append({'candidate_count':len(handles),'valid_instances':len(valid),'invalid_instances':len(invalid),'passed':True})
    result={'passed':True,'validator':'jsonschema '+importlib.metadata.version('jsonschema'),
            'rows':rows,'new_dependency_installs':0,'real_provider_schema_qualification':False}
    with output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result))


if __name__=='__main__':main()
