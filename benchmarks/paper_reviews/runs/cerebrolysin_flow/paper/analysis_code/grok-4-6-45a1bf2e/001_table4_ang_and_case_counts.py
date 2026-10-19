table4_pos = {
  5: {'ang': 2, 'cm': '+'},
  6: {'ang': 1, 'cm': '+'},
  10: {'ang': 3, 'cm': '+'},
  13: {'ang': 3, 'cm': '+'},
  19: {'ang': 2, 'cm': '+'},
  21: {'ang': 3, 'cm': '+'},
  28: {'ang': None, 'cm': '+'},
}
table4_neg = {
  7: {'ang': 2},
  9: {'ang': 1},
  12: {'ang': 1},
  17: {'ang': 1},
  18: {'ang': 2},
  23: {'ang': 2},
  24: {'ang': 1},
  25: {'ang': 1},
  26: {'ang': 1},
  27: {'ang': 1},
}
pos_ang = [v['ang'] for v in table4_pos.values() if v['ang'] is not None]
neg_ang = [v['ang'] for v in table4_neg.values()]
print('n_pos', len(table4_pos))
print('n_neg', len(table4_neg))
print('n_table4', len(table4_pos)+len(table4_neg))
print('pos_ang_values', pos_ang)
print('pos_ang_n', len(pos_ang))
print('pos_ang_mean', sum(pos_ang)/len(pos_ang))
print('pos_ang_sum', sum(pos_ang))
print('neg_ang_values', neg_ang)
print('neg_ang_mean', sum(neg_ang)/len(neg_ang))
print('neg_ang_sum', sum(neg_ang))
# reported 2.57 for pos if scores only 2 and 3
print('18/7', 18/7)
print('14/6', 14/6)
print('13/5', 13/5)
print('13/10', 13/10)
# completers vs table4
completed = {10,11,17,24,27, 9,12,13,18,25,26,29, 5,6,7}
table4 = set(table4_pos)|set(table4_neg)
print('completed_not_in_table4', sorted(completed-table4))
print('table4_not_completed', sorted(table4-completed))
print('n_completed', len(completed))
# vecuronium rats
vec = {19,21,28,29}
print('vec_in_table4', sorted(vec & table4))
print('vec_completed', sorted(vec & completed))
print('vec_not_in_table4', sorted(vec-table4))
