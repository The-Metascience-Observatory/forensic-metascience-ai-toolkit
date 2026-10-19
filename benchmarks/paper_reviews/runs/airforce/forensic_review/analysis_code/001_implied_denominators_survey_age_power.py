from math import sqrt, erf

def round_half_up(x, nd):
    p = 10 ** nd
    return int(x * p + 0.5) / p if x >= 0 else int(x * p - 0.5) / p

def grim_ns(pct, decimals, nmin, nmax):
    hits = []
    for n in range(nmin, nmax+1):
        for k in range(0, n+1):
            val = 100.0 * k / n
            # banker's vs half-up: check both by rounding with python round and formatted
            if round(val, decimals) == pct or float(f'{val:.{decimals}f}') == pct:
                hits.append((n, k, val))
                break
    return hits

items = [
    ('video_brief_effective', 95.89, 2),
    ('inperson_brief_effective', 98.63, 2),
    ('video_confident', 90.41, 2),
    ('inperson_confident', 100.0, 0),
    ('video_daily', 14.86, 2),
    ('inperson_daily', 34.25, 2),
    ('video_mostdays', 37.84, 2),
    ('inperson_mostdays', 63.01, 2),
    ('video_never', 20.27, 2),
    ('inperson_never', 8.22, 2),
    ('video_mski', 31.25, 2),
    ('inperson_mski', 17.72, 2),
    ('video_bsi', 15.0, 0),
    ('inperson_bsi', 5.06, 2),
    ('video_medhold', 1.27, 2),
    ('inperson_medhold', 1.27, 2),
    ('video_recycle_fit', 2.50, 2),
    ('inperson_recycle_fit', 2.53, 2),
    ('inperson_recycle_admin', 1.27, 2),
]
print('IMPLIED DENOMINATORS n in 50..90 (first matching k per n):')
for name, pct, dec in items:
    hits = grim_ns(pct, dec, 50, 90)
    # keep those near 73-80
    near = [h for h in hits if h[0] in range(70, 86)]
    print(name, 'pct', pct, 'n_hits_70_85', near[:12], 'n_total_hits', len(hits))

# Age two-sample t (Student equal var and Welch)
m1, s1, n1 = 21.0, 3.0, 80
m2, s2, n2 = 23.0, 5.0, 79
sp = sqrt(((n1-1)*s1**2 + (n2-1)*s2**2) / (n1+n2-2))
t_eq = (m1-m2) / (sp * sqrt(1/n1 + 1/n2))
df_eq = n1+n2-2
se_w = sqrt(s1**2/n1 + s2**2/n2)
t_w = (m1-m2) / se_w
df_w = (s1**2/n1 + s2**2/n2)**2 / ((s1**2/n1)**2/(n1-1) + (s2**2/n2)**2/(n2-1))

def t_sf_approx(t, df):
    # two-sided p from regularized incomplete beta or normal fallback
    # use Welch-Satterthwaite with a t->p via py; try math.erf as z approx if needed
    z = abs(t)
    # Abramowitz-like: use survival of Student-t via beta
    try:
        from statistics import NormalDist
        p_z = 2*NormalDist().cdf(-z)
    except Exception:
        p_z = 2*(1-0.5*(1+erf(z/sqrt(2))))
    return p_z

print('\nAGE')
print('sp', sp, 't_eq', t_eq, 'df_eq', df_eq)
print('t_welch', t_w, 'df_w', df_w)
print('two-sided normal-approx p from |t_eq|', t_sf_approx(t_eq, df_eq))
print('two-sided normal-approx p from |t_w|', t_sf_approx(t_w, df_w))

# try scipy
try:
    from scipy.stats import t as tdist
    p_eq = 2*tdist.sf(abs(t_eq), df_eq)
    p_w = 2*tdist.sf(abs(t_w), df_w)
    print('scipy Student p', p_eq, 'Welch p', p_w)
except Exception as e:
    print('scipy unavailable', e)

# BMI
mb1, sb1 = 24.1, 2.6
mb2, sb2 = 24.0, 2.8
spb = sqrt(((n1-1)*sb1**2 + (n2-1)*sb2**2)/(n1+n2-2))
tb = (mb1-mb2)/(spb*sqrt(1/n1+1/n2))
print('\nBMI t_eq', tb, 'normal-approx p', t_sf_approx(tb, n1+n2-2))
try:
    from scipy.stats import t as tdist
    print('BMI scipy p', 2*tdist.sf(abs(tb), n1+n2-2))
except Exception:
    pass

# Risk reductions as printed
mski1, mski2 = 0.3125, 0.1772
arr_m = mski1-mski2
rrr_m = arr_m/mski1
nnt_m = 1/arr_m
print('\nMSKI ARR', arr_m, 'RRR', rrr_m, 'NNT', nnt_m, 'per40', 40/nnt_m)
print('reported ARR 13.5 RRR 43 NNIPB 7.4 prevent 5.4')

bsi1, bsi2 = 0.15, 0.0506
arr_b = bsi1-bsi2
rrr_b = arr_b/bsi1
nnt_b = 1/arr_b
print('BSI ARR', arr_b, 'RRR', rrr_b, 'NNT', nnt_b, 'per40', 40/nnt_b)
print('reported ARR 10 RRR 66 NNIPB 10 prevent 4')

# binary SDs for effect size
for label, p in [('mski_v', 0.3125), ('mski_i', 0.1772), ('bsi_v', 0.15), ('bsi_i', 0.0506)]:
    print(label, 'sd', sqrt(p*(1-p)))

# Power: two-proportion for 25% relative increase, n=77, power 0.99, alpha 0.05
# Need baseline p. Try several baselines
print('\nPOWER two-proportion n=77 each, alpha=0.05 two-sided, delta = 1.25*p0')
try:
    from statsmodels.stats.power import NormalIndPower
    from statsmodels.stats.proportion import proportion_effectsize
    nip = NormalIndPower()
    for p0 in [0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.1486, 0.3784]:
        p1 = p0 * 1.25
        if p1 >= 1:
            continue
        es = proportion_effectsize(p1, p0)
        pw = nip.power(es, nobs1=77, alpha=0.05, ratio=1, alternative='two-sided')
        n_for_99 = nip.solve_power(es, power=0.99, alpha=0.05, ratio=1, alternative='two-sided')
        print(f'p0={p0:.4f} p1={p1:.4f} h={es:.4f} power_n77={pw:.4f} n_for_99={n_for_99}')
    # 25 percentage POINTS
    for p0 in [0.10, 0.15, 0.20, 0.40, 0.50]:
        p1 = p0 + 0.25
        if p1 >= 1:
            continue
        es = proportion_effectsize(p1, p0)
        pw = nip.power(es, nobs1=77, alpha=0.05, ratio=1, alternative='two-sided')
        n_for_99 = nip.solve_power(es, power=0.99, alpha=0.05, ratio=1, alternative='two-sided')
        print(f'ADD25 p0={p0:.4f} p1={p1:.4f} h={es:.4f} power_n77={pw:.4f} n_for_99={n_for_99}')
except Exception as e:
    print('statsmodels fail', e)
    # manual Cohen h and normal power
    import math
    def cohen_h(p1, p2):
        return 2*math.asin(sqrt(p1)) - 2*math.asin(sqrt(p2))
    def power_two_prop(p0, p1, n, alpha=0.05):
        h = abs(cohen_h(p1, p0))
        se = 1/sqrt(n/2)  # for h, se = sqrt(1/n1+1/n2)=sqrt(2/n)
        # z power: 1-beta = Phi( h/sqrt(2/n) - zcrit )
        zcrit = 1.959964
        z = h / sqrt(2/n) - zcrit
        from math import erf
        def Phi(z):
            return 0.5*(1+erf(z/sqrt(2)))
        return Phi(z), h
    for p0 in [0.10, 0.15, 0.20, 0.30, 0.40, 0.50, 0.1486]:
        p1 = min(0.999, p0*1.25)
        pw, h = power_two_prop(p0, p1, 77)
        print(f'manual rel25 p0={p0} p1={p1} h={h:.4f} approx_power={pw:.4f}')
    for p0 in [0.15, 0.40, 0.50]:
        p1 = p0+0.25
        pw, h = power_two_prop(p0, p1, 77)
        print(f'manual add25 p0={p0} p1={p1} h={h:.4f} approx_power={pw:.4f}')
