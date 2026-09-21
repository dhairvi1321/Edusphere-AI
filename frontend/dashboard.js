/* ===== INIT ===== */
Auth.requireAuth();

const session = Auth.getSession();
const firstName = session?.name?.split(' ')[0] || session?.email?.split('@')[0] || 'Student';

document.getElementById('sidebarName').textContent = firstName;
document.getElementById('sidebarEmail').textContent = session?.email || '';
document.getElementById('sidebarAvatar').textContent = firstName[0].toUpperCase();
document.getElementById('dashGreeting').textContent = `Welcome back, ${firstName}!`;
document.getElementById('todayDate').textContent = new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });

/* ===== STATE ===== */
let subjects = [], assignments = [], exams = [];
let assignmentFilter = 'all';

/* ===== NAVIGATION ===== */
function switchSection(name) {
  document.querySelectorAll('.dash-section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.sidebar-link').forEach(l => l.classList.remove('active'));
  document.getElementById(`section-${name}`).classList.add('active');
  document.querySelector(`[data-section="${name}"]`).classList.add('active');
  if (window.innerWidth <= 768) document.getElementById('sidebar').classList.remove('open');
}

document.querySelectorAll('.sidebar-link').forEach(link => {
  link.addEventListener('click', e => {
    e.preventDefault();
    switchSection(link.dataset.section);
  });
});

/* Sidebar toggle (mobile) */
document.getElementById('sidebarToggle').addEventListener('click', () => {
  document.getElementById('sidebar').classList.toggle('open');
});

/* ===== TOAST ===== */
function showToast(msg, type = 'success') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = `toast ${type} show`;
  setTimeout(() => t.classList.remove('show'), 3000);
}

/* ===== MODALS ===== */
function openModal(id) { document.getElementById(id).classList.add('open'); }
function closeModal(id) { document.getElementById(id).classList.remove('open'); }

document.querySelectorAll('[data-modal]').forEach(btn => {
  btn.addEventListener('click', () => closeModal(btn.dataset.modal));
});

document.querySelectorAll('.modal-overlay').forEach(overlay => {
  overlay.addEventListener('click', e => {
    if (e.target === overlay) closeModal(overlay.id);
  });
});

/* ===== HELPERS ===== */
function daysUntil(dateStr) {
  const diff = new Date(dateStr) - new Date(new Date().toDateString());
  return Math.ceil(diff / 86400000);
}

function formatDate(dateStr) {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function priorityBadge(p) {
  return `<span class="priority-badge priority-${p}">${p.charAt(0).toUpperCase() + p.slice(1)}</span>`;
}

function daysBadge(days) {
  if (days < 0) return `<span class="exam-days-badge days-past">Past</span>`;
  if (days <= 3) return `<span class="exam-days-badge days-soon">In ${days}d</span>`;
  if (days <= 7) return `<span class="exam-days-badge days-upcoming">In ${days}d</span>`;
  return `<span class="exam-days-badge days-far">In ${days}d</span>`;
}

function subjectName(id) {
  return subjects.find(s => s.id === id)?.name || '—';
}

function populateSubjectSelects() {
  const opts = `<option value="">— No Subject —</option>` +
    subjects.map(s => `<option value="${s.id}">${s.name}</option>`).join('');
  document.getElementById('assignmentSubject').innerHTML = opts;
  document.getElementById('examSubject').innerHTML = opts;
}

/* ===== FETCH ALL DATA ===== */
async function loadAll() {
  [subjects, assignments, exams] = await Promise.all([
    Auth.apiFetch('/academics/subjects/'),
    Auth.apiFetch('/academics/assignments/'),
    Auth.apiFetch('/academics/exams/')
  ]);
  subjects = subjects || [];
  assignments = assignments || [];
  exams = exams || [];

  populateSubjectSelects();
  renderStats();
  renderOverviewLists();
  renderSubjects();
  renderAssignments();
  renderExams();
}

/* ===== STATS ===== */
function renderStats() {
  const pending = assignments.filter(a => !a.is_completed).length;
  const done = assignments.filter(a => a.is_completed).length;
  const upcoming = exams.filter(e => daysUntil(e.exam_date) >= 0).length;
  document.getElementById('statSubjects').textContent = subjects.length;
  document.getElementById('statPending').textContent = pending;
  document.getElementById('statDone').textContent = done;
  document.getElementById('statExams').textContent = upcoming;
}

/* ===== OVERVIEW LISTS ===== */
function renderOverviewLists() {
  // Upcoming exams (next 3)
  const upcoming = exams
    .filter(e => daysUntil(e.exam_date) >= 0)
    .sort((a, b) => new Date(a.exam_date) - new Date(b.exam_date))
    .slice(0, 4);

  const examEl = document.getElementById('upcomingExamsList');
  if (!upcoming.length) {
    examEl.innerHTML = `<div class="dash-empty">No upcoming exams 🎉</div>`;
  } else {
    examEl.innerHTML = upcoming.map(e => {
      const days = daysUntil(e.exam_date);
      return `<div class="dash-list-item">
        <div class="dash-list-dot" style="background:${days <= 3 ? '#f87171' : days <= 7 ? '#fbbf24' : '#34d399'}"></div>
        <div class="dash-list-info">
          <div class="dash-list-name">${e.title}</div>
          <div class="dash-list-meta">${subjectName(e.subject)} · ${formatDate(e.exam_date)}</div>
        </div>
        ${daysBadge(days)}
      </div>`;
    }).join('');
  }

  // Due soon assignments (pending, sorted by due date)
  const due = assignments
    .filter(a => !a.is_completed && a.due_date)
    .sort((a, b) => new Date(a.due_date) - new Date(b.due_date))
    .slice(0, 4);

  const dueEl = document.getElementById('dueSoonList');
  if (!due.length) {
    dueEl.innerHTML = `<div class="dash-empty">No pending assignments 🎉</div>`;
  } else {
    dueEl.innerHTML = due.map(a => {
      const days = daysUntil(a.due_date);
      return `<div class="dash-list-item">
        <div class="dash-list-dot" style="background:${a.priority === 'high' ? '#f87171' : a.priority === 'medium' ? '#fbbf24' : '#34d399'}"></div>
        <div class="dash-list-info">
          <div class="dash-list-name">${a.title}</div>
          <div class="dash-list-meta">${subjectName(a.subject)} · Due ${formatDate(a.due_date)}</div>
        </div>
        ${priorityBadge(a.priority)}
      </div>`;
    }).join('');
  }
}

/* ===== SUBJECTS ===== */
function renderSubjects() {
  const el = document.getElementById('subjectsList');
  if (!subjects.length) {
    el.innerHTML = `<div class="dash-empty" style="grid-column:1/-1">No subjects yet. Add your first subject!</div>`;
    return;
  }
  el.innerHTML = subjects.map(s => {
    const topics = s.topics || [];
    const done = topics.filter(t => t.is_completed).length;
    const pct = topics.length ? Math.round((done / topics.length) * 100) : 0;
    return `<div class="subject-card">
      <div class="subject-card-header">
        <div class="subject-card-name">${s.name}</div>
      </div>
      ${s.description ? `<div class="subject-card-desc">${s.description}</div>` : ''}
      <div class="subject-progress-wrap">
        <div class="subject-progress-label">
          <span>Syllabus Progress</span>
          <span>${done}/${topics.length} topics</span>
        </div>
        <div class="progress-bar-wrap">
          <div class="progress-bar" style="width:${pct}%"></div>
        </div>
      </div>
      ${topics.length ? `<div class="subject-topics">
        ${topics.map(t => `
          <div class="topic-item">
            <div class="topic-check ${t.is_completed ? 'done' : ''}" onclick="toggleTopic(${t.id}, ${!t.is_completed})"></div>
            <span class="topic-name ${t.is_completed ? 'done' : ''}">${t.title}</span>
            <button class="icon-btn danger" onclick="deleteTopic(${t.id})" title="Delete topic">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none"><path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
            </button>
          </div>`).join('')}
      </div>` : ''}
      <div class="subject-card-actions">
        <button class="btn btn-ghost" onclick="openAddTopic(${s.id})">+ Topic</button>
        <button class="btn btn-ghost" onclick="openEditSubject(${s.id})">Edit</button>
        <button class="btn btn-ghost" style="color:#f87171" onclick="deleteSubject(${s.id})">Delete</button>
      </div>
    </div>`;
  }).join('');
}

/* ===== ASSIGNMENTS ===== */
function renderAssignments() {
  const el = document.getElementById('assignmentsList');
  let filtered = assignments;
  if (assignmentFilter === 'pending') filtered = assignments.filter(a => !a.is_completed);
  if (assignmentFilter === 'completed') filtered = assignments.filter(a => a.is_completed);

  if (!filtered.length) {
    el.innerHTML = `<div class="dash-empty">No assignments found.</div>`;
    return;
  }

  el.innerHTML = `<table class="dash-table">
    <thead>
      <tr>
        <th>Title</th>
        <th>Subject</th>
        <th>Due Date</th>
        <th>Priority</th>
        <th>Status</th>
        <th>Actions</th>
      </tr>
    </thead>
    <tbody>
      ${filtered.map(a => `<tr>
        <td>${a.title}</td>
        <td>${subjectName(a.subject)}</td>
        <td>${formatDate(a.due_date)}</td>
        <td>${priorityBadge(a.priority)}</td>
        <td><span class="status-badge ${a.is_completed ? 'status-done' : 'status-pending'}">${a.is_completed ? 'Done' : 'Pending'}</span></td>
        <td>
          <div class="row-actions">
            <button class="icon-btn" onclick="toggleAssignment(${a.id}, ${!a.is_completed})" title="${a.is_completed ? 'Mark pending' : 'Mark done'}">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none"><path d="M20 6L9 17l-5-5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
            </button>
            <button class="icon-btn" onclick="openEditAssignment(${a.id})" title="Edit">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
            </button>
            <button class="icon-btn danger" onclick="deleteAssignment(${a.id})" title="Delete">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none"><polyline points="3 6 5 6 21 6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M19 6l-1 14H6L5 6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M10 11v6M14 11v6M9 6V4h6v2" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
            </button>
          </div>
        </td>
      </tr>`).join('')}
    </tbody>
  </table>`;
}

/* ===== EXAMS ===== */
function renderExams() {
  const el = document.getElementById('examsList');
  if (!exams.length) {
    el.innerHTML = `<div class="dash-empty" style="grid-column:1/-1">No exams yet. Add your first exam!</div>`;
    return;
  }
  const sorted = [...exams].sort((a, b) => new Date(a.exam_date) - new Date(b.exam_date));
  el.innerHTML = sorted.map(e => {
    const days = daysUntil(e.exam_date);
    return `<div class="exam-card">
      <div class="exam-card-top">
        <div>
          <div class="exam-card-title">${e.title}</div>
          <div class="exam-card-subject">${subjectName(e.subject)}</div>
        </div>
        ${daysBadge(days)}
      </div>
      <div class="exam-card-date">📅 ${formatDate(e.exam_date)}</div>
      ${e.notes ? `<div class="exam-card-notes">${e.notes}</div>` : ''}
      <div class="exam-card-actions">
        <button class="icon-btn" onclick="openEditExam(${e.id})" title="Edit">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
        </button>
        <button class="icon-btn danger" onclick="deleteExam(${e.id})" title="Delete">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none"><polyline points="3 6 5 6 21 6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M19 6l-1 14H6L5 6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M10 11v6M14 11v6M9 6V4h6v2" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
        </button>
      </div>
    </div>`;
  }).join('');
}

/* ===== SUBJECT CRUD ===== */
document.getElementById('addSubjectBtn').addEventListener('click', () => {
  document.getElementById('subjectModalTitle').textContent = 'Add Subject';
  document.getElementById('subjectId').value = '';
  document.getElementById('subjectName').value = '';
  document.getElementById('subjectDesc').value = '';
  openModal('subjectModal');
});

function openEditSubject(id) {
  const s = subjects.find(x => x.id === id);
  document.getElementById('subjectModalTitle').textContent = 'Edit Subject';
  document.getElementById('subjectId').value = s.id;
  document.getElementById('subjectName').value = s.name;
  document.getElementById('subjectDesc').value = s.description || '';
  openModal('subjectModal');
}

document.getElementById('subjectForm').addEventListener('submit', async e => {
  e.preventDefault();
  const id = document.getElementById('subjectId').value;
  const body = {
    name: document.getElementById('subjectName').value.trim(),
    description: document.getElementById('subjectDesc').value.trim()
  };
  const res = id
    ? await Auth.apiFetch(`/academics/subjects/${id}/`, { method: 'PUT', body: JSON.stringify(body) })
    : await Auth.apiFetch('/academics/subjects/', { method: 'POST', body: JSON.stringify(body) });
  if (res) { closeModal('subjectModal'); showToast(id ? 'Subject updated!' : 'Subject added!'); await loadAll(); }
  else showToast('Something went wrong.', 'error');
});

async function deleteSubject(id) {
  if (!confirm('Delete this subject and all its topics?')) return;
  const res = await fetch(`http://127.0.0.1:8000/api/academics/subjects/${id}/`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${Auth.getToken()}` }
  });
  if (res.ok) { showToast('Subject deleted.'); await loadAll(); }
  else showToast('Delete failed.', 'error');
}

/* ===== TOPIC CRUD ===== */
function openAddTopic(subjectId) {
  document.getElementById('topicSubjectId').value = subjectId;
  document.getElementById('topicTitle').value = '';
  openModal('topicModal');
}

document.getElementById('topicForm').addEventListener('submit', async e => {
  e.preventDefault();
  const body = {
    subject: parseInt(document.getElementById('topicSubjectId').value),
    title: document.getElementById('topicTitle').value.trim()
  };
  const res = await Auth.apiFetch('/academics/topics/', { method: 'POST', body: JSON.stringify(body) });
  if (res) { closeModal('topicModal'); showToast('Topic added!'); await loadAll(); }
  else showToast('Something went wrong.', 'error');
});

async function toggleTopic(id, completed) {
  await Auth.apiFetch(`/academics/topics/${id}/`, { method: 'PATCH', body: JSON.stringify({ is_completed: completed }) });
  await loadAll();
}

async function deleteTopic(id) {
  const res = await fetch(`http://127.0.0.1:8000/api/academics/topics/${id}/`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${Auth.getToken()}` }
  });
  if (res.ok) { showToast('Topic removed.'); await loadAll(); }
}

/* ===== ASSIGNMENT CRUD ===== */
document.getElementById('addAssignmentBtn').addEventListener('click', () => {
  document.getElementById('assignmentModalTitle').textContent = 'Add Assignment';
  document.getElementById('assignmentId').value = '';
  document.getElementById('assignmentTitle').value = '';
  document.getElementById('assignmentSubject').value = '';
  document.getElementById('assignmentDue').value = '';
  document.getElementById('assignmentPriority').value = 'medium';
  openModal('assignmentModal');
});

function openEditAssignment(id) {
  const a = assignments.find(x => x.id === id);
  document.getElementById('assignmentModalTitle').textContent = 'Edit Assignment';
  document.getElementById('assignmentId').value = a.id;
  document.getElementById('assignmentTitle').value = a.title;
  document.getElementById('assignmentSubject').value = a.subject || '';
  document.getElementById('assignmentDue').value = a.due_date || '';
  document.getElementById('assignmentPriority').value = a.priority;
  openModal('assignmentModal');
}

document.getElementById('assignmentForm').addEventListener('submit', async e => {
  e.preventDefault();
  const id = document.getElementById('assignmentId').value;
  const subVal = document.getElementById('assignmentSubject').value;
  const body = {
    title: document.getElementById('assignmentTitle').value.trim(),
    subject: subVal ? parseInt(subVal) : null,
    due_date: document.getElementById('assignmentDue').value || null,
    priority: document.getElementById('assignmentPriority').value
  };
  const res = id
    ? await Auth.apiFetch(`/academics/assignments/${id}/`, { method: 'PUT', body: JSON.stringify(body) })
    : await Auth.apiFetch('/academics/assignments/', { method: 'POST', body: JSON.stringify(body) });
  if (res) { closeModal('assignmentModal'); showToast(id ? 'Assignment updated!' : 'Assignment added!'); await loadAll(); }
  else showToast('Something went wrong.', 'error');
});

async function toggleAssignment(id, completed) {
  await Auth.apiFetch(`/academics/assignments/${id}/`, { method: 'PATCH', body: JSON.stringify({ is_completed: completed }) });
  await loadAll();
}

async function deleteAssignment(id) {
  if (!confirm('Delete this assignment?')) return;
  const res = await fetch(`http://127.0.0.1:8000/api/academics/assignments/${id}/`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${Auth.getToken()}` }
  });
  if (res.ok) { showToast('Assignment deleted.'); await loadAll(); }
  else showToast('Delete failed.', 'error');
}

/* ===== EXAM CRUD ===== */
document.getElementById('addExamBtn').addEventListener('click', () => {
  document.getElementById('examModalTitle').textContent = 'Add Exam';
  document.getElementById('examId').value = '';
  document.getElementById('examTitle').value = '';
  document.getElementById('examSubject').value = '';
  document.getElementById('examDate').value = '';
  document.getElementById('examNotes').value = '';
  openModal('examModal');
});

function openEditExam(id) {
  const e = exams.find(x => x.id === id);
  document.getElementById('examModalTitle').textContent = 'Edit Exam';
  document.getElementById('examId').value = e.id;
  document.getElementById('examTitle').value = e.title;
  document.getElementById('examSubject').value = e.subject || '';
  document.getElementById('examDate').value = e.exam_date;
  document.getElementById('examNotes').value = e.notes || '';
  openModal('examModal');
}

document.getElementById('examForm').addEventListener('submit', async e => {
  e.preventDefault();
  const id = document.getElementById('examId').value;
  const subVal = document.getElementById('examSubject').value;
  const body = {
    title: document.getElementById('examTitle').value.trim(),
    subject: subVal ? parseInt(subVal) : null,
    exam_date: document.getElementById('examDate').value,
    notes: document.getElementById('examNotes').value.trim()
  };
  const res = id
    ? await Auth.apiFetch(`/academics/exams/${id}/`, { method: 'PUT', body: JSON.stringify(body) })
    : await Auth.apiFetch('/academics/exams/', { method: 'POST', body: JSON.stringify(body) });
  if (res) { closeModal('examModal'); showToast(id ? 'Exam updated!' : 'Exam added!'); await loadAll(); }
  else showToast('Something went wrong.', 'error');
});

async function deleteExam(id) {
  if (!confirm('Delete this exam?')) return;
  const res = await fetch(`http://127.0.0.1:8000/api/academics/exams/${id}/`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${Auth.getToken()}` }
  });
  if (res.ok) { showToast('Exam deleted.'); await loadAll(); }
  else showToast('Delete failed.', 'error');
}

/* ===== FILTER BUTTONS ===== */
document.querySelectorAll('.filter-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    assignmentFilter = btn.dataset.filter;
    renderAssignments();
  });
});

/* ===== LOAD ===== */
loadAll();
