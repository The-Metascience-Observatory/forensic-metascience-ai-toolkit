import math
try:
    from scipy import stats
    has_scipy = True
except Exception as e:
    has_scipy = False
    print('scipy missing', e)

# binary SDs from reconstructed counts
def sd_prop(k, n):
    p = k/n
    return p, math.sqrt(p*(1-p))

print('MSKI video', sd_prop(25,80))
print('MSKI inperson', sd_prop(14,79))
print('BSI video', sd_prop(12,80))
print('BSI inperson', sd_prop(4,79))
print('daily video 11/74', sd_prop(11,74))
print('daily inperson 25/73', sd_prop(25,73))

# age t-test
m1,s1,n1=21.0,3.0,80
m2,s2,n2=23.0,5.0,79
# equal variance
sp2=((n1-1)*s1**2+(n2-1)*s2**2)/(n1+n2-2)
se=math.sqrt(sp2*(1/n1+1/n2))
t=(m1-m2)/se
df=n1+n2-2
print('age pooled t', t, 'df', df)
if has_scipy:
    p=2*stats.t.sf(abs(t), df)
    print('age pooled p', p)
    # welch
    sew=math.sqrt(s1**2/n1+s2**2/n2)
    tw=(m1-m2)/sew
    # welch df
    num=(s1**2/n1+s2**2/n2)**2
    den=(s1**2/n1)**2/(n1-1)+(s2**2/n2)**2/(n2-1)
    dfw=num/den
    pw=2*stats.t.sf(abs(tw), dfw)
    print('age welch t', tw, 'df', dfw, 'p', pw)
    # BMI
    bm1,bs1,bn1=24.1,2.6,80
    bm2,bs2,bn2=24.0,2.8,79
    sp2b=((bn1-1)*bs1**2+(bn2-1)*bs2**2)/(bn1+bn2-2)
    seb=math.sqrt(sp2b*(1/bn1+1/bn2))
    tb=(bm1-bm2)/seb
    pb=2*stats.t.sf(abs(tb), bn1+bn2-2)
    print('BMI t', tb, 'p', pb)

# power 0.80 n=77
try:
    from statsmodels.stats.power import NormalIndPower
    from statsmodels.stats.proportion import proportion_effectsize
    nip=NormalIndPower()
    h80=nip.solve_power(nobs1=77, power=0.80, alpha=0.05, ratio=1.0, alternative='two-sided')
    h90=nip.solve_power(nobs1=77, power=0.90, alpha=0.05, ratio=1.0, alternative='two-sided')
    h99=nip.solve_power(nobs1=77, power=0.99, alpha=0.05, ratio=1.0, alternative='two-sided')
    print('h for n=77 power 0.80', h80)
    print('h for n=77 power 0.90', h90)
    print('h for n=77 power 0.99', h99)
    # n needed for 25% relative at various baselines, power 0.80 and 0.99
    for pwr in (0.80, 0.99):
        print('--- power', pwr)
        for p1 in (0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.1486):
            p2=min(0.999, p1*1.25)
            es=proportion_effectsize(p2,p1)
            n=nip.solve_power(es, power=pwr, alpha=0.05, ratio=1.0, alternative='two-sided')
            print(f'  rel25 p1={p1} p2={p2:.4f} n={n:.1f}')
        for p1 in (0.15, 0.20, 0.25, 0.30):
            p2=p1+0.25
            es=proportion_effectsize(p2,p1)
            n=nip.solve_power(es, power=pwr, alpha=0.05, ratio=1.0, alternative='two-sided')
            print(f'  pp25 p1={p1} p2={p2:.4f} n={n:.1f}')
    # what p2 with p1=0.15 gives n=77 at power 0.99
    # solve by scan
    print('scan p2 for p1=0.15 n~77 power 0.99')
    for p2 in [x/100 for x in range(20,80)]:
        es=proportion_effectsize(p2,0.15)
        n=nip.solve_power(es, power=0.99, alpha=0.05, ratio=1.0, alternative='two-sided')
        if 70<=n<=85:
            print(f'  p2={p2:.2f} n={n:.1f} h={es:.3f}')
except Exception as e:
    print('power fail', type(e), e)

# chi2 from reconstructed MSKI 25/80 vs 14/79
if has_scipy:
    import numpy as np
    tab=np.array([[25,55],[14,65]])
    chi2,p,dof,exp=stats.chi2_contingency(tab, correction=False)
    chi2c,pc,dofc,expc=stats.chi2_contingency(tab, correction=True)
    print('MSKI chi2 uncorr', chi2, 'p', p, 'corr', chi2c, 'p', pc)
    tabb=np.array([[12,68],[4,75]])
    chi2,p,dof,exp=stats.chi2_contingency(tabb, correction=False)
    chi2c,pc,dofc,expc=stats.chi2_contingency(tabb, correction=True)
    print('BSI chi2 uncorr', chi2, 'p', p, 'corr', chi2c, 'p', pc)
    # survey daily 11/74 vs 25/73
    tabs=np.array([[11,63],[25,48]])
    chi2,p,dof,exp=stats.chi2_contingency(tabs, correction=False)
    print('daily 11/74 vs 25/73 chi2', chi2, 'p', p)
    # if they wrongly used 14.86% of 80 = 11.888 ~12/80 vs 27/79 (34.25% of 79=27.06)
    tabw=np.array([[12,68],[27,52]])
    chi2,p,dof,exp=stats.chi2_contingency(tabw, correction=False)
    print('daily if 12/80 vs 27/79 chi2', chi2, 'p', p)
