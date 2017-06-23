

import sys


unsupported = {}

for line in open(sys.argv[1], encoding='utf-8'):
    if 'rpr.converter' in line:
        msg = line.split('rpr.converter', maxsplit=1)[1].split('ERROR', maxsplit=1)[1].lstrip()
        _, category, message = msg.split(maxsplit=2)
        if 'unsupported' == category:
            name, desc = message.split('<', maxsplit=1)[1].split('>', maxsplit=1)
            unsupported.setdefault(name, set()).add(desc)
        else:
            print(category, message)

for name, descs in unsupported.items():
    print(name, '---->', ';'.join(d.rstrip() for d in descs))
print()

print('UNSUPPORTED:')

for u in sorted(unsupported):
    print('*', u)