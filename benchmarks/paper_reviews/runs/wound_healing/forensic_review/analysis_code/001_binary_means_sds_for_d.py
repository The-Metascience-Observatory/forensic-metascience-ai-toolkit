import math

def sample_sd(k, n):
    p = k / n
    return math.sqrt(n * p * (1 - p) / (n - 1))

rows = [
    ('infection_continuous', 17, 198),
    ('infection_interrupted', 3, 199),
    ('composite_continuous', 33, 198),
    ('composite_interrupted', 9, 199),
    ('gapping_continuous', 10, 198),
    ('gapping_interrupted', 2, 199),
    ('seroma_continuous', 9, 198),
    ('seroma_interrupted', 1, 199),
    ('erythema_continuous', 14, 198),
    ('erythema_interrupted', 4, 199),
]
for name, k, n in rows:
    p = k / n
    sd = sample_sd(k, n)
    print(f'{name}: k={k} n={n} mean={p:.10f} sd={sd:.10f}')
