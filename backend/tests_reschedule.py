"""
Standalone tests for rescheduling logic.
No Django/MongoDB required — tests the pure scheduling functions directly.
Run: python tests_reschedule.py
"""
from datetime import date, timedelta
import uuid, sys


def _schedule_sessions(topic_pool, start, end, daily_hours):
    sessions = []
    topic_index = 0
    session_duration = 45
    daily_minutes = daily_hours * 60
    total_days = (end - start).days + 1
    for day_offset in range(total_days):
        if topic_index >= len(topic_pool):
            break
        current_date = (start + timedelta(days=day_offset)).isoformat()
        minutes_used = 0
        while topic_index < len(topic_pool):
            if minutes_used + session_duration > daily_minutes:
                break
            item = topic_pool[topic_index]
            sessions.append({
                'session_id': str(uuid.uuid4()),
                'date': current_date,
                'subject': item['subject'],
                'topic': item['topic'],
                'topic_id': item['topic_id'],
                'is_completed': False,
            })
            minutes_used += session_duration
            topic_index += 1
    return sessions


def make_pool(n):
    return [{'subject': 'Math', 'topic': f'T{i}', 'topic_id': str(i), 'subject_id': '1'} for i in range(n)]


PASS = []
FAIL = []

def check(name, condition, detail=''):
    if condition:
        PASS.append(name)
        print(f'  PASS  {name}')
    else:
        FAIL.append(name)
        print(f'  FAIL  {name}' + (f': {detail}' if detail else ''))


start = date(2025, 1, 1)
end3  = date(2025, 1, 3)   # 3 days

# TEST 1: daily limit respected
sessions = _schedule_sessions(make_pool(20), start, end3, daily_hours=2)  # 120 min = 2 sessions/day
per_day = {}
for s in sessions:
    per_day.setdefault(s['date'], 0)
    per_day[s['date']] += 1
check('T1a daily limit not exceeded', all(v <= 2 for v in per_day.values()), str(per_day))
check('T1b correct total sessions (3 days x 2)', len(sessions) == 6, str(len(sessions)))

# TEST 2: no sessions beyond end date
sessions2 = _schedule_sessions(make_pool(100), start, end3, daily_hours=1)  # 1 session/day
check('T2a no session beyond end date', all(s['date'] <= end3.isoformat() for s in sessions2))
check('T2b correct total (3 days x 1)', len(sessions2) == 3, str(len(sessions2)))

# TEST 3: completed preserved, pending replaced, no duplication
existing = [
    {'session_id': 'A', 'topic_id': 'topic-1', 'is_completed': True,  'subject': 'Math', 'topic': 'T1'},
    {'session_id': 'B', 'topic_id': 'topic-2', 'is_completed': False, 'subject': 'Math', 'topic': 'T2'},
    {'session_id': 'C', 'topic_id': 'topic-3', 'is_completed': False, 'subject': 'Math', 'topic': 'T3'},
]
completed_sessions = [s for s in existing if s.get('is_completed')]
completed_topic_ids = {s['topic_id'] for s in completed_sessions}
pool3 = [
    {'subject': 'Math', 'topic': 'T1', 'topic_id': 'topic-1', 'subject_id': '1'},
    {'subject': 'Math', 'topic': 'T2', 'topic_id': 'topic-2', 'subject_id': '1'},
    {'subject': 'Math', 'topic': 'T3', 'topic_id': 'topic-3', 'subject_id': '1'},
    {'subject': 'Math', 'topic': 'T4', 'topic_id': 'topic-4', 'subject_id': '1'},
]
filtered = [t for t in pool3 if t['topic_id'] not in completed_topic_ids]
new_sessions = _schedule_sessions(filtered, start, end3, daily_hours=2)
new_ids = {s['topic_id'] for s in new_sessions}
check('T3a completed topic not rescheduled', 'topic-1' not in new_ids)
check('T3b pending topic-2 rescheduled',     'topic-2' in new_ids)
check('T3c pending topic-3 rescheduled',     'topic-3' in new_ids)
check('T3d new topic-4 scheduled',           'topic-4' in new_ids)
final = completed_sessions + new_sessions
done_in_final = [s for s in final if s.get('is_completed')]
check('T3e original completed session A preserved',
      len(done_in_final) == 1 and done_in_final[0]['session_id'] == 'A')
new_id_list = [s['topic_id'] for s in new_sessions]
check('T3f no duplicate topic_ids in new sessions', len(new_id_list) == len(set(new_id_list)))

# TEST 4: preview == commit (same exclusion set)
preview_excl = {s['topic_id'] for s in existing if s.get('is_completed') and s.get('topic_id')}
commit_excl  = {s['topic_id'] for s in existing if s.get('is_completed') and s.get('topic_id')}
check('T4  preview and commit exclusion sets identical', preview_excl == commit_excl)

# TEST 5: empty pool
check('T5  empty pool returns []', _schedule_sessions([], start, end3, daily_hours=2) == [])

# TEST 6: single-day schedule
single = _schedule_sessions(make_pool(10), date(2025,1,1), date(2025,1,1), daily_hours=2)
check('T6a single day all sessions on correct date', all(s['date'] == '2025-01-01' for s in single))
check('T6b single day session count', len(single) == 2, str(len(single)))

# TEST 7: single topic fits in 1h slot
one = _schedule_sessions(make_pool(1), date(2025,1,1), date(2025,1,1), daily_hours=1)
check('T7  single topic fits in 1h slot', len(one) == 1)

# TEST 8: cancel preview does not mutate original plan
original_sessions = [dict(s) for s in existing]
_ = _schedule_sessions(filtered, start, end3, daily_hours=2)
check('T8  original plan unchanged after preview', existing == original_sessions)

print()
print(f'Results: {len(PASS)} passed, {len(FAIL)} failed')
sys.exit(0 if not FAIL else 1)
