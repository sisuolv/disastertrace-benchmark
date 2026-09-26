"""Check: rebuilding the roster (limit=24) from raw reproduces the published G1 episodes byte-for-byte (in memory only)."""
import json, sys
sys.path.insert(0, '/tmp/dt_review/agent_data')
from common import *
import build_v18_dev_episodes as b
rep = b.build_roster(DATA, limit=24, run_id=RUN_ID)
pub = json.load(open(ART / 'G1_DEV_EPISODES_V3.json'))
same = json.dumps(rep['episodes'], sort_keys=True) == json.dumps(pub['episodes'], sort_keys=True)
print('rebuilt episodes identical to published:', same, '| status counts equal:', rep['qualification_status_counts_by_checkpoint'] == pub['qualification_status_counts_by_checkpoint'])
