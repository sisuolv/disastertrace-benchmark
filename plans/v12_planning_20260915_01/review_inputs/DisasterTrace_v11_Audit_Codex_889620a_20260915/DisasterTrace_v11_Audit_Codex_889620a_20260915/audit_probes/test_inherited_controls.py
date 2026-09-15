"""Focused executable controls and boundary regressions; no API, weather fetch or GPU."""
import copy
import datetime as dt
import json
import math
import pytest
from probe_loader import A,C,E,F,N,S,T,TC

DAY=TC.DAY  # constant relocated in v11; inherited assertions unchanged
START=int(dt.datetime(2018,1,2,tzinfo=dt.timezone.utc).timestamp())*1000000

def product(day=0, values=(31.,20.), mins=(-2.,2.)):
    return {'target_date':(dt.date(2018,1,2)+dt.timedelta(days=day)).isoformat(),
            'day_index':day+1,'forecast_max_members_C':list(values),'forecast_min_members_C':list(mins)}
def row(days=1, variable='daily_max_2m_temperature', operator='ge', threshold=30.):
    return {'target':{'units':'C','physical_start':START,'physical_end':START+days*DAY,
                     'variable':variable,'event_operator':operator,'threshold':threshold},
            'cutoff':START-DAY//2,'common':{'daily_products':[product(i) for i in range(days)]}}
def claim(lower=100.,upper=1000.,lower_closed=True,upper_closed=True):
    return {'visibility':{'lower':lower,'upper':upper,'lower_closed':lower_closed,'upper_closed':upper_closed},
            'temperature_c':5.,'dewpoint_c':3.}
def feature_inputs():
    target={'physical_start':START,'physical_end':START+3600000000,'entity':'station:TEST'}
    disclosed={'q':{'query_id':'q','status':'disclosed_product_fact','reports':[{'observation_time':START-7200000000}]}}
    return target,disclosed,START-3600000000

@pytest.mark.parametrize('variable,operator,threshold,expected',[
 ('daily_max_2m_temperature','ge',30,0.5),('daily_max_2m_temperature','lt',30,0.5),
 ('daily_min_2m_temperature','lt',0,0.5),('daily_min_2m_temperature','ge',0,0.5)])
def test_daily_calculators_agree(variable,operator,threshold,expected):
    r=row(variable=variable,operator=operator,threshold=threshold)
    assert F.temperature_ensemble_probability(r)==T.event_probability(r)==expected

def test_same_member_three_day_not_product_of_marginals():
    r=row(3,'min_of_3_daily_max_2m_temperature')
    assert F.temperature_ensemble_probability(r)==T.event_probability(r)==0.5
    assert 0.5 != 0.5**3

def test_member_path_permutation_matters_only_when_not_common():
    r=row(3,'min_of_3_daily_max_2m_temperature')
    common=copy.deepcopy(r)
    for p in common['common']['daily_products']:
        p['forecast_max_members_C'].reverse();p['forecast_min_members_C'].reverse()
    assert T.event_probability(common)==T.event_probability(r)
    common['common']['daily_products'][1]['forecast_max_members_C'].reverse()
    assert T.event_probability(common)==0

def test_three_day_ice_max_along_member():
    r=row(3,'max_of_3_daily_max_2m_temperature','lt',0)
    for p in r['common']['daily_products']:p['forecast_max_members_C']=[-1.,3.]
    assert F.temperature_ensemble_probability(r)==T.event_probability(r)==0.5

@pytest.mark.parametrize('mutation',['day0','different_member_count','nonfinite_member','empty_members'])
def test_both_calculators_reject_common_invalid_products(mutation):
    r=row(3,'min_of_3_daily_max_2m_temperature')
    p=r['common']['daily_products'][0]
    if mutation=='day0':p['day_index']=0
    if mutation=='different_member_count':p['forecast_max_members_C'].append(4.)
    if mutation=='nonfinite_member':p['forecast_max_members_C'][0]=float('nan')
    if mutation=='empty_members':p['forecast_max_members_C']=[]
    for fn in (F.temperature_ensemble_probability,T.event_probability):
        with pytest.raises(ValueError):fn(r)

def test_both_calculators_reject_nonfuture_cutoff():
    r=row();r['cutoff']=START
    for fn in (F.temperature_ensemble_probability,T.event_probability):
        with pytest.raises(ValueError):fn(r)

@pytest.mark.parametrize('case',['shifted_utc_day','duplicate_target_date'])
def test_temperature_input_contracts_should_reject_same_bad_row(case):
    r=row()
    if case=='shifted_utc_day':
        r['target']['physical_start']+=DAY//2;r['target']['physical_end']+=DAY//2
    else:
        r['common']['daily_products'].append(product(values=(35.,35.)))
    with pytest.raises(ValueError):T.event_probability(r)
    with pytest.raises(ValueError):F.temperature_ensemble_probability(r)

@pytest.mark.parametrize('value',[True,'0.5',-0.1,1.1])
def test_temperature_response_strict_type(value):
    with pytest.raises(ValueError):F.parse_temperature(json.dumps({'probability':value}))

def test_temperature_response_duplicate_key_rejected():
    with pytest.raises(ValueError):F.parse_temperature('{"probability":0.1,"probability":0.9}')

def test_temperature_single_fence_and_no_prose():
    assert F.parse_temperature('```json\n{"probability":0.5}\n```')==(0.5,{'whole_json_fence':True})
    with pytest.raises((ValueError,TypeError)):F.parse_temperature('text {"probability":0.5}')

@pytest.mark.parametrize('lower,upper,lc,uc',[(0,402.336,True,False),(9656.064,'+inf',False,False),(16093.44,16093.44,True,True)])
def test_feature_parser_valid_native_intervals(lower,upper,lc,uc):
    c=claim(lower,upper,lc,uc)
    assert F.parse_features(json.dumps({'slots':{'q':c}}),['q'])[0]['q']==c

def test_feature_parser_rejects_unread_slot():
    with pytest.raises(ValueError):F.parse_features(json.dumps({'slots':{'q':claim()}}),[])

def test_feature_parser_rejects_empty_finite_interval():
    with pytest.raises(ValueError):F.parse_features(json.dumps({'slots':{'q':claim(1,1,False,False)}}),['q'])

def test_feature_parser_should_reject_infinite_lower_endpoint():
    # A lower endpoint at +infinity contains no finite native visibility value.
    c=claim('+inf','+inf',True,True)
    with pytest.raises(ValueError):F.parse_features(json.dumps({'slots':{'q':c}}),['q'])

def test_open_closed_feature_collision_is_documented_diagnostic():
    target,disclosed,at=feature_inputs()
    a,b=claim(0,1000,True,True),claim(0,1000,True,False)
    assert S.classify(E.interval_from_dict(a['visibility']),'lt',1000)=='undetermined'
    assert S.classify(E.interval_from_dict(b['visibility']),'lt',1000)=='supported'
    fa=N.feature_vector(target,None,['q'],disclosed,at=at,claims={'q':a})
    fb=N.feature_vector(target,None,['q'],disclosed,at=at,claims={'q':b})
    assert fa==fb # Characterization, not a scientific success criterion or Gold repair.

def test_mask_age_does_not_encode_numeric_values():
    target,disclosed,at=feature_inputs()
    a,b=claim(),claim(4000,4000)
    a['temperature_c']=-10;b['temperature_c']=20
    fa=N.feature_vector(target,None,['q'],disclosed,at=at,claims={'q':a},mode='mask_age')
    fb=N.feature_vector(target,None,['q'],disclosed,at=at,claims={'q':b},mode='mask_age')
    assert fa==fb

def test_future_observation_rejected_with_model_claims():
    target,d,at=feature_inputs();d['q']['reports'][0]['observation_time']=START
    with pytest.raises(ValueError):N.feature_vector(target,None,['q'],d,at=at,claims={'q':claim()})

def test_softmax_threshold_coherence():
    bank={'feature_version':N.FEATURE_VERSION,'feature_names':['x'],'mean':[0.],'scale':[1.],
          'coefficients':[[1.],[-1.],[0.]],'intercepts':[0.,0.,0.],'mapping_version':'probe'}
    for x in [-1000.,-5.,0.,5.,1000.]:
        p=N.predict_features(bank,{'x':x})
        assert 0<=p['1000']<=p['5000']<=1
        assert math.isclose(sum(p['classes']),1)

@pytest.mark.parametrize('values,expected',[([0.8,0.2],[0.5,0.5]),([0.1,0.4],[0.1,0.4]),([0.9,0.6,0.3],[0.6,0.6,0.6])])
def test_coherent_cdf(values,expected):
    assert C.coherent_cdf(values,['same']*len(values))==pytest.approx(expected)

def test_cdf_rejects_different_information():
    with pytest.raises(ValueError):C.coherent_cdf([0.8,0.2],['a','b'])

def test_fixed_total_prior_invariant_to_splitting_weights():
    original=[(0.1,0,1.),(0.8,1,1.)]
    split=[(p,y,0.25) for p,y,_ in original for _ in range(4)]
    assert C.fit_fixed_prior(original)==C.fit_fixed_prior(split)

def test_zero_harm_gate_can_only_accept_identical_binary_probability():
    p={'kind':'brier_harm_limit','max_pointwise_harm':0.0}
    for a in [0.,0.2,0.5,0.9,1.]:
        for b in [0.,0.2,0.5,0.9,1.]:
            assert A.decide(p,current=a,candidate=b,previously_adopted=False)['adopt']==(a==b)

def test_gate_bound_checks_both_outcomes():
    for a,b in [(0.1,0.2),(0.9,0.2),(0.5,0.7)]:
        r=A.decide({'kind':'brier_harm_limit','max_pointwise_harm':0.2},current=a,candidate=b,previously_adopted=False)
        assert r['max_pointwise_harm']==max((b-y)**2-(a-y)**2 for y in [0,1])

def test_ecc_no_mutation_rank_and_member_count():
    products=[product(values=(20.,10.,30.),mins=(2.,-1.,3.))]
    old=copy.deepcopy(products)
    bank={k:{'a':0.,'b':1.,'log_c':-5.,'log_d':0.} for k in ['min','max']}
    new,tr=T.ecc_products(products,bank)
    assert products==old and tr['minmax_projections']==0
    for field in ['forecast_min_members_C','forecast_max_members_C']:
        assert sorted(range(3),key=lambda i:old[0][field][i])==sorted(range(3),key=lambda i:new[0][field][i])

def test_ecc_minmax_repair_is_reported():
    products=[product(values=(1.,2.),mins=(-2.,-1.))]
    bank={'min':{'a':30.,'b':0.,'log_c':0.,'log_d':-5.},'max':{'a':0.,'b':0.,'log_c':0.,'log_d':-5.}}
    new,tr=T.ecc_products(products,bank)
    assert tr['minmax_projections']==2
    assert all(a<=b for a,b in zip(new[0]['forecast_min_members_C'],new[0]['forecast_max_members_C']))
