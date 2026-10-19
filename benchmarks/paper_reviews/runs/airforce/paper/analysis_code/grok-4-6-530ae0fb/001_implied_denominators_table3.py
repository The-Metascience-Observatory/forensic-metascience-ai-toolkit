from decimal import Decimal, ROUND_HALF_UP

def round_half_up(x, nd=2):
    q = Decimal('1').scaleb(-nd)
    return float(Decimal(str(x)).quantize(q, rounding=ROUND_HALF_UP))

def matches(pct, n, nd=2):
    hits = []
    for k in range(0, n+1):
        p = 100.0 * k / n
        if round_half_up(p, nd) == pct:
            hits.append(k)
    return hits

# Survey percentages as printed, header ns, and nearby ns
survey = {
    'video_found_effective': (95.89, 2),
    'video_confident': (90.41, 2),
    'video_daily': (14.86, 2),
    'video_most': (37.84, 2),
    'video_never': (20.27, 2),
    'inperson_found_effective': (98.63, 2),
    'inperson_confident': (100.0, 0),  # printed 100
    'inperson_daily': (34.25, 2),
    'inperson_most': (63.01, 2),
    'inperson_never': (8.22, 2),
}
injury = {
    'video_mski': (31.25, 2, 80),
    'inperson_mski': (17.72, 2, 79),
    'video_bsi': (15.0, 0, 80),  # printed 15
    'inperson_bsi': (5.06, 2, 79),
    'video_medhold': (1.27, 2, 80),
    'inperson_medhold': (1.27, 2, 79),
    'video_recycle_fit': (2.50, 2, 80),
    'inperson_recycle_fit': (2.53, 2, 79),
    'inperson_recycle_admin': (1.27, 2, 79),
}

print('=== SURVEY: ns 60-80 that produce each percentage ===')
for name, (pct, nd) in survey.items():
    good = []
    for n in range(60, 81):
        ks = matches(pct, n, nd)
        if ks:
            good.append((n, ks))
    print(name, 'pct', pct, 'nd', nd, 'solutions', good[-12:] if len(good)>12 else good)

print('\n=== SURVEY joint video-only (found, confident, daily, most, never) shared n ===')
video_names = ['video_found_effective','video_confident','video_daily','video_most','video_never']
inperson_names = ['inperson_found_effective','inperson_confident','inperson_daily','inperson_most','inperson_never']
for n in range(60, 81):
    ok = True
    detail = {}
    for name in video_names:
        pct, nd = survey[name]
        ks = matches(pct, n, nd)
        if not ks:
            ok = False
            break
        detail[name] = ks
    if ok:
        print('VIDEO joint n', n, detail)

for n in range(60, 81):
    ok = True
    detail = {}
    for name in inperson_names:
        pct, nd = survey[name]
        ks = matches(pct, n, nd)
        if not ks:
            ok = False
            break
        detail[name] = ks
    if ok:
        print('INPERSON joint n', n, detail)

print('\n=== Brief-effectiveness pair (found+confident) vs compliance pair (daily+most+never) ===')
for n in range(60, 81):
    be = all(matches(survey[nm][0], n, survey[nm][1]) for nm in ['video_found_effective','video_confident'])
    co = all(matches(survey[nm][0], n, survey[nm][1]) for nm in ['video_daily','video_most','video_never'])
    if be or co:
        print('video n', n, 'brief_ok', be, 'comp_ok', co)
for n in range(60, 81):
    be = all(matches(survey[nm][0], n, survey[nm][1]) for nm in ['inperson_found_effective','inperson_confident'])
    co = all(matches(survey[nm][0], n, survey[nm][1]) for nm in ['inperson_daily','inperson_most','inperson_never'])
    if be or co:
        print('inperson n', n, 'brief_ok', be, 'comp_ok', co)

print('\n=== INJURY/TRAINING at printed n ===')
for name, (pct, nd, n) in injury.items():
    ks = matches(pct, n, nd)
    print(name, 'n', n, 'pct', pct, 'counts', ks, 'implied_from_pct', round(pct/100.0*n, 4))
    if not ks:
        # nearest
        best = min(range(n+1), key=lambda k: abs(100.0*k/n - pct))
        print('  nearest k', best, 'gives', round_half_up(100.0*best/n, nd), 'raw', 100.0*best/n)

print('\n=== Vitamin C %DV ===')
amount_ug = 100.0
amount_mg = 100.0
for ref in [85, 90, 120, 80, 75, 60]:
    print('100 mg /', ref, 'mg *100 =', round(100*amount_mg/ref, 4))
    print('100 ug /', ref, 'mg *100 =', round(100*(amount_ug/1000.0)/ref, 6))

print('\n=== RRR/ARR/NNT ===')
mski_c, mski_t = 31.25, 17.72
arr_mski = mski_c - mski_t
rrr_mski = arr_mski / mski_c * 100
nnt_mski = 100/arr_mski
print('MSKI ARR', arr_mski, 'reported 13.5; RRR', rrr_mski, 'reported 43; NNT', nnt_mski, 'reported 7.4')
print('40/7.4 =', 40/7.4, 'reported 5.4 MSKI prevented')
bsi_c, bsi_t = 15.0, 5.06
arr_bsi = bsi_c - bsi_t
rrr_bsi = arr_bsi / bsi_c * 100
nnt_bsi = 100/arr_bsi
print('BSI ARR', arr_bsi, 'reported 10; RRR', rrr_bsi, 'reported 66; NNT', nnt_bsi, 'reported 10')
print('40/10 =', 40/10, 'reported 4 BSI prevented')

print('\n=== Age t-test (for handoff) ===')
import math
m1, s1, n1 = 21.0, 3.0, 80
m2, s2, n2 = 23.0, 5.0, 79
sp2 = ((n1-1)*s1**2 + (n2-1)*s2**2) / (n1+n2-2)
se = math.sqrt(sp2*(1/n1+1/n2))
t = (m1-m2)/se
print('pooled sd', math.sqrt(sp2), 'se', se, 't', t, 'df', n1+n2-2)
# welch
sew = math.sqrt(s1**2/n1 + s2**2/n2)
tw = (m1-m2)/sew
print('welch se', sew, 't', tw)

print('\n=== Power reverse engineer two-proportion ===')
# n=77 per arm, alpha 0.05 two-sided, power 0.99, 25% relative increase
try:
    from statsmodels.stats.power import NormalIndPower
    from statsmodels.stats.proportion import proportion_effectsize
    nip = NormalIndPower()
    print('statsmodels available')
    # try baselines
    for p1 in [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.1486, 0.3784]:
        p2 = p1 * 1.25  # 25% relatively greater
        if p2 >= 1:
            continue
        es = proportion_effectsize(p2, p1)
        nobs = nip.solve_power(es, power=0.99, alpha=0.05, ratio=1.0, alternative='two-sided')
        print(f'p1={p1:.4f} p2={p2:.4f} h={es:.4f} n_per={nobs}')
    print('--- 25 percentage POINTS greater ---')
    for p1 in [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]:
        p2 = p1 + 0.25
        if p2 >= 1:
            continue
        es = proportion_effectsize(p2, p1)
        nobs = nip.solve_power(es, power=0.99, alpha=0.05, ratio=1.0, alternative='two-sided')
        print(f'p1={p1:.4f} p2={p2:.4f} h={es:.4f} n_per={nobs}')
    print('--- solve for effect given n=77 power=0.99 ---')
    es_needed = nip.solve_power(nobs1=77, power=0.99, alpha=0.05, ratio=1.0, alternative='two-sided')
    print('Cohen h needed', es_needed)
except Exception as e:
    print('statsmodels fail', type(e), e)
