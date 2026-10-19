from math import sqrt
from scipy.stats import t as tdist, chi2, fisher_exact, norm

n1, n2 = 80, 79

def ttest(m1,s1,n1,m2,s2,n2, equal_var=True):
    if equal_var:
        sp = sqrt(((n1-1)*s1**2 + (n2-1)*s2**2)/(n1+n2-2))
        se = sp*sqrt(1/n1+1/n2)
        df = n1+n2-2
        tv = (m1-m2)/se
        p = 2*tdist.sf(abs(tv), df)
        return tv, df, p, se
    se = sqrt(s1**2/n1 + s2**2/n2)
    df = (s1**2/n1 + s2**2/n2)**2 / ((s1**2/n1)**2/(n1-1) + (s2**2/n2)**2/(n2-1))
    tv = (m1-m2)/se
    p = 2*tdist.sf(abs(tv), df)
    return tv, df, p, se

print('Printed age 21 vs 23, sd 3 vs 5')
print('equal-var', ttest(21,3,80,23,5,79, True))
print('welch', ttest(21,3,80,23,5,79, False))

# rounding box: means to 0 dp, sds to 0 dp
# 21 => [20.5, 21.5]; 23 => [22.5, 23.5]; 3 => [2.5, 3.5]; 5 => [4.5, 5.5]
# search grid for MAX p (most NS)
import numpy as np
m1s = np.linspace(20.5, 21.4999, 40)
m2s = np.linspace(22.5, 23.4999, 40)
s1s = np.linspace(2.5, 3.4999, 20)
s2s = np.linspace(4.5, 5.4999, 20)
max_p = 0
best = None
min_p = 1
for m1 in (20.5, 21.0, 21.4999):
    for m2 in (22.5, 23.0, 23.4999):
        for s1 in (2.5, 3.0, 3.4999):
            for s2 in (4.5, 5.0, 5.4999):
                tv, df, p, se = ttest(m1,s1,80,m2,s2,79, True)
                if p > max_p:
                    max_p = p
                    best = ('eq', m1,s1,m2,s2,tv,p)
                tvw, dfw, pw, sew = ttest(m1,s1,80,m2,s2,79, False)
                if pw > max_p:
                    max_p = pw
                    best = ('welch', m1,s1,m2,s2,tvw,pw)
print('corner max p', max_p, best)

# denser: closest means 21.4999 vs 22.5, largest sds 3.4999 and 5.4999
print('closest+largestSD equal-var', ttest(21.4999, 3.4999, 80, 22.5, 5.4999, 79, True))
print('closest+largestSD welch', ttest(21.4999, 3.4999, 80, 22.5, 5.4999, 79, False))
# if SDs were 1 decimal internally but printed 0? skip

# CACE for BSI and MSKI
# ITT ARR BSI 12/80 - 4/79
arr_bsi = 12/80 - 4/79
arr_mski = 25/80 - 14/79
print('\nITT ARR BSI', arr_bsi, 'MSKI', arr_mski)
# compliance diffs using implied counts
# daily: 11/74 vs 25/73
# never: 15/74 vs 6/73  so took-at-all = 1-never: 59/74 vs 67/73
never_v, never_i = 15/74, 6/73
took_v, took_i = 1-never_v, 1-never_i
daily_v, daily_i = 11/74, 25/73
most_v, most_i = 28/74, 46/73
print('took any', took_v, took_i, 'diff', took_i-took_v)
print('daily', daily_v, daily_i, 'diff', daily_i-daily_v)
print('most days', most_v, most_i, 'diff', most_i-most_v)
# If most-days is exclusive of daily, in-person daily+most+never = (25+46+6)/73
print('inperson exclusive sum counts', 25+46+6, 'of 73', (25+46+6)/73)
print('video exclusive sum counts', 11+28+15, 'of 74', (11+28+15)/74)

for name, arr, dcomp in [
    ('BSI via daily-diff', arr_bsi, daily_i-daily_v),
    ('BSI via took-any-diff', arr_bsi, took_i-took_v),
    ('BSI via mostdays-diff', arr_bsi, most_i-most_v),
    ('MSKI via daily-diff', arr_mski, daily_i-daily_v),
    ('MSKI via took-any-diff', arr_mski, took_i-took_v),
    ('MSKI via mostdays-diff', arr_mski, most_i-most_v),
]:
    cace = arr/dcomp if dcomp else None
    print(name, 'ARR', arr, 'delta_comp', dcomp, 'CACE', cace, 'CACE_vs_ctrl_risk', None if cace is None else cace/(12/80 if 'BSI' in name else 25/80))

# chi-square MSKI 25/80 vs 14/79 and BSI 12/80 vs 4/79
def chi2_2x2(a,c,b,d):
    # a cases1, c noncases1, b cases2, d noncases2
    n = a+b+c+d
    # Pearson
    table = np.array([[a,c],[b,d]], dtype=float)
    # wait rows are groups, cols outcome yes/no: [[25,55],[14,65]]
    tab = np.array([[a, c],[b, d]], dtype=float)
    rsum = tab.sum(1, keepdims=True)
    csum = tab.sum(0, keepdims=True)
    exp = rsum @ csum / tab.sum()
    stat = ((tab-exp)**2/exp).sum()
    p = chi2.sf(stat, 1)
    # yates
    staty = ((np.abs(tab-exp)-0.5)**2/exp).sum()
    py = chi2.sf(staty, 1)
    # fisher
    oddsr, pf = fisher_exact([[a,c],[b,d]])
    print(f'a={a} n1={a+c} b={b} n2={b+d} chi2={stat:.4f} p={p:.5f} yates={staty:.4f} py={py:.5f} fisher={pf:.5f}')
    return stat, p

print('\nMSKI')
chi2_2x2(25,55,14,65)
print('BSI')
chi2_2x2(12,68,4,75)
print('daily 11/74 vs 25/73')
chi2_2x2(11,63,25,48)
print('daily if they used n=80,79 with rounded pct: 12/80=15% not 14.86; 27/79=34.18')
# if they used header n wrongly: round 14.86% of 80 = 11.888 -> 12; 34.25% of 79 = 27.0575
print('if k from pct*header: video daily', round(0.1486*80), 'inperson', round(0.3425*79))

# survey n missing
print('\nmissing survey brief n=73 vs 80/79: video missing', 80-73, 'inperson missing', 79-73)
print('compliance video n=74 missing', 80-74, 'inperson n=73 missing', 79-73)
print('pct missing video brief', (80-73)/80, 'inperson', (79-73)/79)

# Vitamin C %DV
print('\nVitC 100 ug / 120 mg *100 =', 0.1/120*100)
print('VitC 100 mg / 120 mg *100 =', 100/120*100)
print('VitC 100 mg / 85 mg *100 =', 100/85*100)
print('VitC 100 ug / 120 ug *100 =', 100/120*100)
