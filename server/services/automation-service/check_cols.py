import json, urllib.request, sys
BASE = 'http://localhost:6333'
for col in ['business_context', 'user_data_entries']:
    try:
        info = json.loads(urllib.request.urlopen(BASE+'/collections/'+col, timeout=5).read())
        cfg = info['result']['config']['params']['vectors']
        pts = info['result']['points_count']
        print('%s  dim=%d  points=%d' % (col, cfg['size'], pts))
    except Exception as e:
        print('%s  ERROR: %s' % (col, e))
