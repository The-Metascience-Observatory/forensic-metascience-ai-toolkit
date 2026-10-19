import math

def bernoulli(k, n):
    p = k / n
    sd = math.sqrt(p * (1 - p))
    print(f"k={k} n={n} p={p:.10f} sd={sd:.10f}")
    return p, sd

print("infection")
bernoulli(17, 198)
bernoulli(3, 199)
print("composite")
bernoulli(33, 198)
bernoulli(9, 199)
print("gapping")
bernoulli(10, 198)
bernoulli(2, 199)
