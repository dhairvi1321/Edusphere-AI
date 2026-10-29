"""
Standalone regression tests for study-plan generation logic.
No Django/MongoDB required — tests pure scheduling and pool-building helpers.
Run: python tests_study_plan.py
"""
import sys
import uuid
from datetime import date, timedelta, datetime

# ── Inline copies of the pure functions under test ──────────────────────────

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
                'subject_id': item['subject_id'],
                'topic': item['topic'],
                'topic_id': item['topic_id'],
                'duration': f'{session_duration} min',
                'duration_minutes': session_duration,
                'is_completed': False,
            })
            minutes_used += session_duration
            topic_index += 1
    return sessions


def _simulate_build_pool(subjects_data, excluded=None, filter_subject_ids=None):
    """
    Simulates _build_session_pool without MongoDB.
    subjects_data: list of dicts {id, name, topics: [{id, title, is_completed, difficulty}]}
    """
    excluded = excluded or set()
    DIFFICULTY_RANK = {'hard': 0, 'medium': 1, 'easy': 2}
    if filter_subject_ids:
        subjects_data = [s for s in subjects_data if s['id'] in filter_subject_ids]
    pool = []
    for subject in subjects_data:
        for topic in subject.get('topics', []):
            if topic.get('is_completed') or topic['id'] in excluded:
                continue
            pool.append({
                'subject': subject['name'],
                'subject_id': subject['id'],
                'topic': topic['title'],
                'topic_id': topic['id'],
                '_exam_key': datetime.max.date(),
                '_assignment_key': (2, datetime.max.date(), 3),
                '_difficulty_key': DIFFICULTY_RANK.get(topic.get('difficulty', 'medium'), 1),
            })
    return pool


# ── Test harness ─────────────────────────────────────────────────────────────

PASS, FAIL = [], []

def check(name, condition, detail=''):
    if condition:
        PASS.append(name)
        print(f'  PASS  {name}')
    else:
        FAIL.append(name)
        print(f'  FAIL  {name}' + (f': {detail}' if detail else ''))


START = date(2025, 6, 1)
END7  = date(2025, 6, 7)   # 7 days
END1  = date(2025, 6, 1)   # 1 day


# ── TC-SP-01: Subject with manually entered topics ───────────────────────────
subjects_manual = [{'id': 's1', 'name': 'Math', 'topics': [
    {'id': 't1', 'title': 'Algebra', 'is_completed': False, 'difficulty': 'medium'},
    {'id': 't2', 'title': 'Calculus', 'is_completed': False, 'difficulty': 'hard'},
]}]
pool = _simulate_build_pool(subjects_manual)
sessions = _schedule_sessions(pool, START, END7, daily_hours=2)
check('TC-SP-01a manual topics appear in pool', len(pool) == 2, str(len(pool)))
check('TC-SP-01b sessions generated from manual topics', len(sessions) == 2, str(len(sessions)))


# ── TC-SP-02: Subject with imported syllabus topics ──────────────────────────
# Imported topics are identical in structure to manually added ones
subjects_imported = [{'id': 's2', 'name': 'Software Engineering', 'topics': [
    {'id': str(uuid.uuid4()), 'title': 'SDLC Models', 'is_completed': False, 'difficulty': 'medium'},
    {'id': str(uuid.uuid4()), 'title': 'Agile Methods', 'is_completed': False, 'difficulty': 'easy'},
    {'id': str(uuid.uuid4()), 'title': 'Testing Strategies', 'is_completed': False, 'difficulty': 'hard'},
]}]
pool2 = _simulate_build_pool(subjects_imported)
sessions2 = _schedule_sessions(pool2, START, END7, daily_hours=2)
check('TC-SP-02a imported topics in pool', len(pool2) == 3, str(len(pool2)))
check('TC-SP-02b sessions generated from imported topics', len(sessions2) == 3, str(len(sessions2)))


# ── TC-SP-03: Multiple selected subjects ─────────────────────────────────────
subjects_multi = [
    {'id': 's3', 'name': 'Data Science', 'topics': [
        {'id': 'ds1', 'title': 'Pandas', 'is_completed': False, 'difficulty': 'easy'},
        {'id': 'ds2', 'title': 'NumPy', 'is_completed': False, 'difficulty': 'medium'},
    ]},
    {'id': 's4', 'name': 'Network Technology', 'topics': [
        {'id': 'nt1', 'title': 'TCP/IP', 'is_completed': False, 'difficulty': 'hard'},
    ]},
]
pool3 = _simulate_build_pool(subjects_multi, filter_subject_ids=['s3', 's4'])
sessions3 = _schedule_sessions(pool3, START, END7, daily_hours=2)
check('TC-SP-03a all subjects included', len(pool3) == 3, str(len(pool3)))
check('TC-SP-03b sessions from multiple subjects', len(sessions3) == 3, str(len(sessions3)))
subject_names = {s['subject'] for s in sessions3}
check('TC-SP-03c both subjects represented', subject_names == {'Data Science', 'Network Technology'}, str(subject_names))


# ── TC-SP-04: Selected subject with zero topics ───────────────────────────────
subjects_empty = [{'id': 's5', 'name': 'Empty Subject', 'topics': []}]
pool4 = _simulate_build_pool(subjects_empty)
sessions4 = _schedule_sessions(pool4, START, END7, daily_hours=2)
check('TC-SP-04a empty subject produces empty pool', len(pool4) == 0, str(len(pool4)))
check('TC-SP-04b empty pool produces no sessions', len(sessions4) == 0, str(len(sessions4)))


# ── TC-SP-05: Mix of subjects with and without topics ────────────────────────
subjects_mix = [
    {'id': 's6', 'name': 'Has Topics', 'topics': [
        {'id': 'ht1', 'title': 'Topic A', 'is_completed': False, 'difficulty': 'medium'},
    ]},
    {'id': 's7', 'name': 'No Topics', 'topics': []},
]
pool5 = _simulate_build_pool(subjects_mix)
sessions5 = _schedule_sessions(pool5, START, END7, daily_hours=2)
check('TC-SP-05a only non-empty subject contributes', len(pool5) == 1, str(len(pool5)))
check('TC-SP-05b session from subject with topics', sessions5[0]['subject'] == 'Has Topics')


# ── TC-SP-06: Completed topics are excluded ───────────────────────────────────
subjects_completed = [{'id': 's8', 'name': 'Physics', 'topics': [
    {'id': 'p1', 'title': 'Mechanics', 'is_completed': True,  'difficulty': 'hard'},
    {'id': 'p2', 'title': 'Optics',    'is_completed': False, 'difficulty': 'medium'},
]}]
pool6 = _simulate_build_pool(subjects_completed)
check('TC-SP-06a completed topic excluded from pool', len(pool6) == 1, str(len(pool6)))
check('TC-SP-06b only incomplete topic in pool', pool6[0]['topic_id'] == 'p2')

# Completed sessions: excluded_topic_ids excludes already-done topics
pool6_excl = _simulate_build_pool(subjects_completed, excluded={'p2'})
check('TC-SP-06c excluded topic_id not in pool', len(pool6_excl) == 0, str(len(pool6_excl)))


# ── TC-SP-07: Valid exam date range and daily study limit ─────────────────────
subjects_7 = [{'id': 's9', 'name': 'Chemistry', 'topics': [
    {'id': f'c{i}', 'title': f'Topic {i}', 'is_completed': False, 'difficulty': 'medium'}
    for i in range(10)
]}]
pool7 = _simulate_build_pool(subjects_7)
# 3 days × 2h = 6 sessions (45 min each, 2 per day)
sessions7 = _schedule_sessions(pool7, START, date(2025, 6, 3), daily_hours=2)
per_day = {}
for s in sessions7:
    per_day.setdefault(s['date'], 0)
    per_day[s['date']] += 1
check('TC-SP-07a daily limit respected (max 2/day)', all(v <= 2 for v in per_day.values()), str(per_day))
check('TC-SP-07b correct total sessions', len(sessions7) == 6, str(len(sessions7)))
check('TC-SP-07c unscheduled topics counted', len(pool7) - len(sessions7) == 4)


# ── TC-SP-08: Empty pool (no topics at all) ───────────────────────────────────
sessions8 = _schedule_sessions([], START, END7, daily_hours=2)
check('TC-SP-08  empty pool returns empty sessions', sessions8 == [])


# ── TC-SP-09: Subject filter respected (user isolation simulation) ────────────
subjects_isolation = [
    {'id': 'user_a_s1', 'name': 'User A Subject', 'topics': [
        {'id': 'ua_t1', 'title': 'Topic UA', 'is_completed': False, 'difficulty': 'medium'},
    ]},
    {'id': 'user_b_s1', 'name': 'User B Subject', 'topics': [
        {'id': 'ub_t1', 'title': 'Topic UB', 'is_completed': False, 'difficulty': 'medium'},
    ]},
]
# User A only sees their own subject
pool_a = _simulate_build_pool(subjects_isolation, filter_subject_ids=['user_a_s1'])
check('TC-SP-09a user A only sees own subject', len(pool_a) == 1 and pool_a[0]['subject_id'] == 'user_a_s1')
pool_b = _simulate_build_pool(subjects_isolation, filter_subject_ids=['user_b_s1'])
check('TC-SP-09b user B only sees own subject', len(pool_b) == 1 and pool_b[0]['subject_id'] == 'user_b_s1')


# ── TC-SP-10: Session completion tracking (is_completed preserved) ────────────
pool10 = [{'subject': 'Bio', 'subject_id': 's10', 'topic': 'Cells', 'topic_id': 'bio1',
           '_exam_key': datetime.max.date(), '_assignment_key': (2, datetime.max.date(), 3), '_difficulty_key': 1}]
sessions10 = _schedule_sessions(pool10, START, END1, daily_hours=2)
check('TC-SP-10a new session starts as not completed', sessions10[0]['is_completed'] is False)
# Simulate toggling
sessions10[0]['is_completed'] = True
check('TC-SP-10b session can be marked completed', sessions10[0]['is_completed'] is True)
# Completed topic excluded from next pool build
pool10_after = _simulate_build_pool(
    [{'id': 's10', 'name': 'Bio', 'topics': [
        {'id': 'bio1', 'title': 'Cells', 'is_completed': True, 'difficulty': 'medium'}
    ]}]
)
check('TC-SP-10c completed topic excluded from next pool', len(pool10_after) == 0)


# ── TC-SP-11: Exam filter merge — exam with no subject does not wipe subject filter ──
def _simulate_exam_filter_merge(filter_subject_ids, filter_exam_ids, exams):
    """Mirrors the fixed _build_session_pool exam filter logic."""
    if filter_exam_ids:
        exam_subject_ids = {e['subject_id'] for e in exams if e['id'] in filter_exam_ids and e.get('subject_id')}
        merged = set(filter_subject_ids or []) | exam_subject_ids
        if merged:
            filter_subject_ids = list(merged)
    return filter_subject_ids

# Exam with no subject_id — selected subjects must be preserved
result = _simulate_exam_filter_merge(['s1', 's2'], ['exam_no_subject'], [{'id': 'exam_no_subject', 'subject_id': None}])
check('TC-SP-11a exam with no subject preserves selected subjects', set(result) == {'s1', 's2'}, str(result))

# Exam with a subject_id — that subject is added to the filter
result2 = _simulate_exam_filter_merge(['s1'], ['exam_with_subject'], [{'id': 'exam_with_subject', 'subject_id': 's3'}])
check('TC-SP-11b exam subject added to filter', set(result2) == {'s1', 's3'}, str(result2))

# No subjects selected, exam has subject — only exam subject used
result3 = _simulate_exam_filter_merge(None, ['exam_only'], [{'id': 'exam_only', 'subject_id': 's5'}])
check('TC-SP-11c no subjects + exam subject = exam subject only', result3 == ['s5'], str(result3))


# ── TC-SP-12: Date range too short for any session ───────────────────────────
pool12 = [{'subject': 'X', 'subject_id': 'sx', 'topic': 'T', 'topic_id': 'tx',
           '_exam_key': datetime.max.date(), '_assignment_key': (2, datetime.max.date(), 3), '_difficulty_key': 1}]
# 1 day, 0 hours — no sessions fit
sessions12 = _schedule_sessions(pool12, START, END1, daily_hours=0)
check('TC-SP-12  zero daily hours produces no sessions', sessions12 == [])


# ── Summary ──────────────────────────────────────────────────────────────────
print()
print(f'Results: {len(PASS)} passed, {len(FAIL)} failed')
sys.exit(0 if not FAIL else 1)
