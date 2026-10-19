completers_cere = {10, 11, 17, 24, 27}
completers_nacl = {9, 12, 13, 18, 25, 26, 29}
completers_ctrl = {5, 6, 7}
completers = completers_cere | completers_nacl | completers_ctrl
named_deaths = {4, 8, 21, 23, 28, 2, 3}  # surgical failure 4; immediate 8,21,23,28; next day 2,3
vecuronium = {19, 21, 28, 29}
table4_pos = {5, 6, 10, 13, 19, 21, 28}
table4_neg = {7, 9, 12, 17, 18, 23, 24, 25, 26, 27}
table4 = table4_pos | table4_neg
all_ids = set(range(1, 31))
mentioned = completers | named_deaths | vecuronium | table4
print('n completers', len(completers), sorted(completers))
print('n table4', len(table4), 'pos', len(table4_pos), 'neg', len(table4_neg))
print('completers not in table4', sorted(completers - table4))
print('table4 not completers', sorted(table4 - completers))
print('table4 not completers and not named deaths', sorted(table4 - completers - named_deaths))
print('vecuronium not completers', sorted(vecuronium - completers))
print('vecuronium not table4', sorted(vecuronium - table4))
print('named deaths also completers (should be empty)', sorted(named_deaths & completers))
print('unmentioned among 1-30', sorted(all_ids - mentioned))
print('mentioned n', len(mentioned))
print('deaths implied 30-completers', 30-len(completers))
print('named deaths n', len(named_deaths))
print('unnamed deaths among unmentioned', sorted(all_ids - mentioned))
# If 21 at 2nd Op, animals that died before 2nd Op = 30-21=9
# named deaths after reaching 2nd Op = 8,21,23,28,2,3 = 6, remaining completers 15, 21-6=15
print('pos in table4 who got vecuronium', sorted(table4_pos & vecuronium))
print('CMAP+ claimed 8 vs table4 pos', len(table4_pos))
