mws = [0.4000, 0.4000, 0.6667, 0.7333, 0.7667, 0.8000, 0.5667, 0.6333]
print('n', len(mws))
print('simple_mean', sum(mws)/len(mws))
print('combined_reported', 0.5611)
print('min', min(mws), 'max', max(mws))
# Table 3
mws3 = [0.6250, 0.8182]
print('table3 simple mean', sum(mws3)/len(mws3))
print('table3 combined reported 0.5611')
# CI widths
print('table2 combined CI width', 0.5766-0.5456)
print('NNTXDIAM CI width', 0.7296-0.0704)
print('Muscle Marlene CI width', 0.8507-0.3993)
print('Muscle Catoi CI width', 1.0-0.5578)
