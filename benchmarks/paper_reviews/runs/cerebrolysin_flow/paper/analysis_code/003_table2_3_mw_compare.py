t2 = [0.4000, 0.4000, 0.6667, 0.7333, 0.7667, 0.8000, 0.5667, 0.6333]
print('Table2 component mean', sum(t2)/len(t2))
print('Table2 combined printed 0.5611')
print('Table3 Muscle Marlene 0.6250 Catoi 0.8182 combined 0.5611')
print('combined below both Table3 components', 0.5611 < 0.6250 and 0.5611 < 0.8182)
print('Table3 p Marlene 0.4146 Catoi 0.4936 match Table2 first two p 0.4146 0.4936', True)
# vecuronium unit
print('80 ug/kg == 0.08 mg/kg', 80/1000 == 0.08)
print('table 0.04-0.05 vs 0.08, fold vs 0.05', 0.08/0.05)
