from collections import Counter

# Table 4 cases as printed (EMG sign, case number)
emg_pos = [5, 6, 10, 13, 19, 21, 28]
emg_neg = [7, 9, 12, 17, 18, 23, 24, 25, 26, 27]
print('n EMG+ Table 4:', len(emg_pos))
print('n EMG- Table 4:', len(emg_neg))
print('n Table 4 total:', len(emg_pos)+len(emg_neg))

completers = {
    'CERE': [10, 11, 17, 24, 27],
    'NaCl': [9, 12, 13, 18, 25, 26, 29],
    'control': [5, 6, 7],
}
completer_ids = sorted(completers['CERE']+completers['NaCl']+completers['control'])
print('n completers listed:', len(completer_ids), completer_ids)

table4_ids = sorted(emg_pos+emg_neg)
print('Table 4 ids:', table4_ids)
print('completers NOT in Table 4:', sorted(set(completer_ids)-set(table4_ids)))
print('Table 4 NOT completers:', sorted(set(table4_ids)-set(completer_ids)))

died_2nd_op_immediate = [8, 21, 23, 28]
died_2nd_op_nextday = [2, 3]
print('named 2nd-Op deaths:', sorted(died_2nd_op_immediate+died_2nd_op_nextday))

# angiogenesis scores as printed in Table 4 Reaction column
ang_pos = {5:2, 6:1, 10:3, 13:3, 19:2, 21:3}  # 28: not listed
ang_neg = {7:2, 9:1, 12:1, 17:1, 18:2, 23:2, 24:1, 25:1, 26:1, 27:1}
print('EMG+ ang scores listed n=', len(ang_pos), 'values', list(ang_pos.values()), 'mean', sum(ang_pos.values())/len(ang_pos))
print('EMG+ if case 28 scored 3:', (sum(ang_pos.values())+3)/7)
print('EMG+ if case 28 scored 2:', (sum(ang_pos.values())+2)/7)
print('sum EMG+ six scores', sum(ang_pos.values()), '18/7=', 18/7, 'needed for 2.57')
print('EMG- ang n=', len(ang_neg), 'sum', sum(ang_neg.values()), 'mean', sum(ang_neg.values())/len(ang_neg))

# Schwann cell scores EMG-
sc_neg = {7:0, 9:1, 12:1, 17:0, 18:3, 23:0, 24:0, 25:1, 26:0, 27:0}
print('EMG- Sc score 0:', sum(1 for v in sc_neg.values() if v==0))
print('EMG- Sc score 1:', sum(1 for v in sc_neg.values() if v==1))
print('EMG- Sc other:', {k:v for k,v in sc_neg.items() if v not in (0,1)})

# vecuronium rats vs completers vs table4
vec = [19, 21, 28, 29]
print('vecuronium not in completers', sorted(set(vec)-set(completer_ids)))
print('vecuronium not in Table 4', sorted(set(vec)-set(table4_ids)))
