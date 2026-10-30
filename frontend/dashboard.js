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
let subjects = [], assignments = [], exams = [], studyPlans = [];
let assignmentFilter = 'all';
let generatedSessions = null, generatedPlanMeta = null;

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

/* ===== ACADEMIC ASSISTANT ===== */
function addAssistantMessage(role, text) {
  const message = document.createElement('div');
  message.className = `assistant-message assistant-message--${role}`;
  message.textContent = text;
  document.getElementById('assistantMessages').appendChild(message);
  message.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
}

document.getElementById('assistantForm').addEventListener('submit', async event => {
  event.preventDefault();
  const input = document.getElementById('assistantQuestion');
  const button = document.getElementById('assistantSubmit');
  const question = input.value.trim();
  if (!question || button.disabled) return;

  addAssistantMessage('user', question);
  input.value = '';
  input.disabled = true;
  button.disabled = true;
  button.textContent = 'Checking…';
  try {
    const result = await Auth.apiFetch('/academics/assistant/ask/', {
      method: 'POST',
      body: JSON.stringify({ question })
    });
    addAssistantMessage('assistant', result?.answer || 'I could not load your academic data just now. Please try again.');
  } catch {
    addAssistantMessage('assistant', 'I could not reach the assistant just now. Please try again.');
  } finally {
    input.disabled = false;
    button.disabled = false;
    button.textContent = 'Ask';
    input.focus();
  }
});

document.querySelectorAll('[data-assistant-question]').forEach(button => {
  button.addEventListener('click', () => {
    const input = document.getElementById('assistantQuestion');
    input.value = button.dataset.assistantQuestion;
    input.focus();
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

window.addEventListener('edusphere:api-error', event => {
  showToast(event.detail || 'Student data is temporarily unavailable. Please try again.', 'error');
});

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

/* ===== TOPIC QUIZZES ===== */
const AI_QUIZ_GENERATION_ENABLED = false;
let currentTopicQuiz = null;
let quizAvailability = null;
let quizQuestionIndex = 0;
let quizAnswers = {};
let quizSubmitting = false;
let bankQuizCreating = false;
let syllabusQuizGenerating = false;
let savedQuizLoading = false;
let activeQuizSyllabus = null;
let pendingQuizSyllabusFile = null;

function fillQuizSubjectSelect() {
  const select = document.getElementById('quizSubjectSelect');
  const placeholder = document.createElement('option');
  placeholder.value = '';
  placeholder.textContent = subjects.length ? 'Choose a subject' : 'No subjects available';
  select.replaceChildren(placeholder);
  subjects.forEach(subject => {
    const option = document.createElement('option');
    option.value = subject.id;
    option.textContent = subject.name;
    select.appendChild(option);
  });
  select.disabled = !subjects.length;
}

function resetQuizSelection(message = 'Choose a subject and topic to find quizzes.') {
  quizAvailability = null;
  currentTopicQuiz = null;
  document.getElementById('topicQuizList').replaceChildren();
  document.getElementById('topicQuizDetail').replaceChildren();
  document.getElementById('quizAttemptHistory').replaceChildren();
  document.getElementById('quizListStatus').textContent = message;
}

function selectedQuizTopicIds() {
  return [...document.querySelectorAll('#quizTopicCheckboxes input[type="checkbox"]:checked')].map(input => input.value);
}

function updateQuizSetupSummary() {
  const subject = subjects.find(item => item.id === document.getElementById('quizSubjectSelect').value);
  const topicIds = selectedQuizTopicIds();
  const count = Number(document.getElementById('quizQuestionCount').value);
  const validCount = Number.isInteger(count) && count >= 1 && count <= 20;
  document.getElementById('quizTopicSelectionCount').textContent = topicIds.length ? `${topicIds.length} topic${topicIds.length === 1 ? '' : 's'} selected` : (subject?.topics?.length ? 'Select one or more topics' : (subject ? 'This subject has no topics yet' : 'Select a subject first'));
  document.getElementById('quizSummarySubject').textContent = `Subject: ${subject?.name || '—'}`;
  document.getElementById('quizSummaryTopics').textContent = `Topics selected: ${topicIds.length}`;
  document.getElementById('quizSummaryCount').textContent = `Questions requested: ${validCount ? count : '—'}`;
  const difficulty = document.getElementById('quizDifficulty').value;
  document.getElementById('quizSummaryDifficulty').textContent = `Difficulty: ${difficulty.charAt(0).toUpperCase()}${difficulty.slice(1)}`;
  const hasSelection = Boolean(subject && topicIds.length);
  const countError = document.getElementById('quizCountError');
  countError.textContent = !validCount ? 'Enter a whole number from 1 to 20.' :
    (hasSelection && !activeQuizSyllabus && quizAvailability !== null && count > quizAvailability ? `Only ${quizAvailability} question(s) at this difficulty are saved. Lower the count or upload a syllabus.` : '');
  document.getElementById('createBankQuizBtn').disabled = bankQuizCreating || Boolean(activeQuizSyllabus) || !hasSelection || !validCount || quizAvailability === null || count > quizAvailability;
  document.getElementById('generateTopicQuizBtn').disabled = !AI_QUIZ_GENERATION_ENABLED || syllabusQuizGenerating || !activeQuizSyllabus || !hasSelection || !validCount;
  document.getElementById('loadTopicQuizzesBtn').disabled = savedQuizLoading || !hasSelection;
}

function renderQuizTopicCheckboxes(topics) {
  const container = document.getElementById('quizTopicCheckboxes');
  container.replaceChildren();
  if (!topics.length) {
    const empty = document.createElement('p');
    empty.className = 'quiz-empty-state';
    empty.textContent = document.getElementById('quizSubjectSelect').value
      ? 'No syllabus topics are saved for this subject yet. Add topics in Subjects or upload a syllabus.'
      : 'Choose a subject to see its syllabus topics.';
    container.appendChild(empty);
    return;
  }
  topics.forEach(topic => {
    const label = document.createElement('label');
    label.className = 'quiz-topic-option';
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.value = topic.id;
    checkbox.dataset.topicName = topic.title;
    checkbox.addEventListener('change', () => {
      label.classList.toggle('is-selected', checkbox.checked);
      updateQuizSetupSummary();
      refreshQuizAvailability();
    });
    const title = document.createElement('span');
    title.textContent = topic.unit ? `${topic.title} · ${topic.unit}` : topic.title;
    label.append(checkbox, title);
    container.appendChild(label);
  });
}

async function refreshQuizAvailability() {
  const subjectId = document.getElementById('quizSubjectSelect').value;
  const topicIds = selectedQuizTopicIds();
  const availability = document.getElementById('quizAvailableCount');
  quizAvailability = null;
  updateQuizSetupSummary();
  if (!subjectId || !topicIds.length) {
    availability.textContent = 'Choose topic(s) to check availability';
    return;
  }
  if (activeQuizSyllabus) {
    quizAvailability = 0;
    availability.textContent = 'Uploaded topics are not saved in the question bank';
    updateQuizSetupSummary();
    return;
  }
  availability.textContent = 'Checking saved questions…';
  const difficulty = document.getElementById('quizDifficulty').value;
  const query = new URLSearchParams({ subject_id: subjectId, topic_ids: topicIds.join(','), difficulty });
  const result = await Auth.apiFetch(`/academics/quizzes/availability/?${query}`);
  if (subjectId !== document.getElementById('quizSubjectSelect').value ||
      topicIds.join(',') !== selectedQuizTopicIds().join(',') ||
      difficulty !== document.getElementById('quizDifficulty').value) return;
  if (!result) {
    availability.textContent = 'Could not check saved question count';
    updateQuizSetupSummary();
    return;
  }
  quizAvailability = result.available_count;
  availability.textContent = quizAvailability
    ? `${quizAvailability} unique question${quizAvailability === 1 ? '' : 's'} available in the saved bank`
    : '0 saved questions. Ask an instructor to add questions or try syllabus AI generation.';
  if (!quizAvailability) {
    document.getElementById('quizListStatus').textContent = 'No questions are saved for these topics yet. Use syllabus AI generation if the backend is configured, or ask an instructor to add curated questions.';
  }
  updateQuizSetupSummary();
}

document.getElementById('quizSubjectSelect').addEventListener('change', event => {
  activeQuizSyllabus = null;
  pendingQuizSyllabusFile = null;
  const fileInput = document.getElementById('quizSyllabusFile');
  fileInput.value = '';
  document.getElementById('quizSyllabusFileMeta').textContent = 'No file selected';
  document.getElementById('quizRemoveSyllabusBtn').hidden = true;
  document.getElementById('quizSyllabusPreviewPanel').hidden = true;
  document.getElementById('quizSyllabusStatus').textContent = event.target.value ? 'Choose a PDF, DOCX, or TXT syllabus to extract topics.' : 'Choose a saved subject before uploading.';
  document.getElementById('quizUploadSyllabusBtn').disabled = !event.target.value;
  document.getElementById('quizSyllabusFile').disabled = !event.target.value;
  document.getElementById('quizSyllabusDropzone').setAttribute('aria-disabled', String(!event.target.value));
  const subject = subjects.find(item => item.id === event.target.value);
  const topics = subject?.topics || [];
  renderQuizTopicCheckboxes(topics);
  document.getElementById('quizTopicSearch').disabled = !topics.length;
  document.getElementById('quizTopicSearch').value = '';
  document.getElementById('quizSelectAllTopics').disabled = !topics.length;
  document.getElementById('quizClearTopics').disabled = !topics.length;
  resetQuizSelection(subject ? 'Select topics to check the saved question bank.' : 'Choose a subject and topics to begin.');
  document.getElementById('quizAvailableCount').textContent = topics.length ? 'Select topic(s) to check availability' : 'No syllabus topics available';
  updateQuizSetupSummary();
});

function setPendingSyllabusFile(file) {
  pendingQuizSyllabusFile = file || null;
  if (file) {
    activeQuizSyllabus = null;
    const subject = subjects.find(item => item.id === document.getElementById('quizSubjectSelect').value);
    renderQuizTopicCheckboxes(subject?.topics || []);
    document.getElementById('quizSyllabusPreviewPanel').hidden = true;
    document.getElementById('quizSyllabusStatus').classList.remove('quiz-status--error');
    document.getElementById('quizTopicSearch').disabled = !(subject?.topics?.length);
    document.getElementById('quizSelectAllTopics').disabled = !(subject?.topics?.length);
    document.getElementById('quizClearTopics').disabled = !(subject?.topics?.length);
    document.getElementById('topicQuizList').replaceChildren();
    document.getElementById('topicQuizDetail').replaceChildren();
    document.getElementById('quizAttemptHistory').replaceChildren();
    quizAvailability = null;
    resetQuizSelection('Upload and extract the syllabus to select its topics.');
    document.getElementById('quizAvailableCount').textContent = 'Extract the uploaded syllabus to identify topics';
  }
  document.getElementById('quizSyllabusFileMeta').textContent = file
    ? `${file.name} · ${(file.size / 1024 / 1024).toFixed(2)} MB`
    : 'No file selected';
  document.getElementById('quizUploadSyllabusBtn').disabled = !file || !document.getElementById('quizSubjectSelect').value;
  document.getElementById('quizRemoveSyllabusBtn').hidden = !file && !activeQuizSyllabus;
  if (file) document.getElementById('quizSyllabusStatus').textContent = 'File selected. It will be checked and extracted by the backend.';
}

const quizSyllabusFileInput = document.getElementById('quizSyllabusFile');
const syllabusDropzone = document.getElementById('quizSyllabusDropzone');
quizSyllabusFileInput.addEventListener('change', event => setPendingSyllabusFile(event.target.files[0]));
syllabusDropzone.addEventListener('click', () => {
  if (!quizSyllabusFileInput.disabled) quizSyllabusFileInput.click();
});
syllabusDropzone.addEventListener('keydown', event => {
  if ((event.key === 'Enter' || event.key === ' ') && !quizSyllabusFileInput.disabled) {
    event.preventDefault();
    quizSyllabusFileInput.click();
  }
});
['dragenter', 'dragover'].forEach(type => syllabusDropzone.addEventListener(type, event => {
  event.preventDefault();
  if (!quizSyllabusFileInput.disabled) syllabusDropzone.classList.add('is-dragging');
}));
['dragleave', 'drop'].forEach(type => syllabusDropzone.addEventListener(type, event => {
  event.preventDefault();
  syllabusDropzone.classList.remove('is-dragging');
}));
syllabusDropzone.addEventListener('drop', event => {
  if (quizSyllabusFileInput.disabled) return;
  const file = event.dataTransfer?.files?.[0];
  if (file) {
    try { quizSyllabusFileInput.files = event.dataTransfer.files; } catch { /* file picker remains available */ }
    setPendingSyllabusFile(file);
  }
});

document.getElementById('quizUploadSyllabusBtn').addEventListener('click', async () => {
  const subjectId = document.getElementById('quizSubjectSelect').value;
  if (!subjectId || !pendingQuizSyllabusFile) return;
  const button = document.getElementById('quizUploadSyllabusBtn');
  button.disabled = true;
  quizSyllabusFileInput.disabled = true;
  document.getElementById('quizRemoveSyllabusBtn').disabled = true;
  syllabusDropzone.setAttribute('aria-disabled', 'true');
  button.textContent = 'Extracting…';
  document.getElementById('quizSyllabusStatus').textContent = 'Uploading temporarily and extracting text on the server…';
  const body = new FormData();
  body.append('subject_id', subjectId);
  body.append('file', pendingQuizSyllabusFile);
  try {
    const result = await Auth.apiFetch('/academics/quizzes/syllabus/', { method: 'POST', body, throwOnError: true });
    if (subjectId !== document.getElementById('quizSubjectSelect').value) return;
    activeQuizSyllabus = { token: result.upload_token, subjectId, topics: result.topics, filename: result.filename };
    renderQuizTopicCheckboxes(result.topics);
    document.getElementById('quizTopicSearch').disabled = !result.topics.length;
    document.getElementById('quizSelectAllTopics').disabled = !result.topics.length;
    document.getElementById('quizClearTopics').disabled = !result.topics.length;
    document.getElementById('quizSyllabusFileMeta').textContent = `${result.filename} · ${result.file_type} · ${result.total_found} topic(s) detected`;
    document.getElementById('quizSyllabusStatus').textContent = `Text extraction complete. ${result.summary} Select the topics to include.`;
    document.getElementById('quizSyllabusSummary').textContent = `${result.summary} Extracted text preview`;
    document.getElementById('quizSyllabusPreview').textContent = result.preview;
    document.getElementById('quizSyllabusPreviewPanel').hidden = false;
    document.getElementById('quizRemoveSyllabusBtn').hidden = false;
    document.getElementById('quizSyllabusStatus').classList.remove('quiz-status--error');
    document.getElementById('quizSyllabusPreviewPanel').hidden = true;
    document.getElementById('quizUploadSyllabusBtn').disabled = false;
    document.getElementById('quizAvailableCount').textContent = 'Choose topic(s) to generate from the uploaded syllabus';
    quizAvailability = null;
    resetQuizSelection('Select extracted topics and question settings before generating.');
    document.getElementById('quizAvailableCount').textContent = 'Uploaded topics use syllabus generation, not the saved question bank';
    document.getElementById('topicQuizList').replaceChildren();
    document.getElementById('topicQuizDetail').replaceChildren();
    document.getElementById('quizAttemptHistory').replaceChildren();
    document.getElementById('quizListStatus').textContent = 'Choose one or more extracted syllabus topics, set the question count and difficulty, then generate.';
    quizAvailability = 0;
  } catch (error) {
    activeQuizSyllabus = null;
    const subject = subjects.find(item => item.id === document.getElementById('quizSubjectSelect').value);
    renderQuizTopicCheckboxes(subject?.topics || []);
    document.getElementById('quizTopicSearch').disabled = !(subject?.topics?.length);
    document.getElementById('quizSelectAllTopics').disabled = !(subject?.topics?.length);
    document.getElementById('quizClearTopics').disabled = !(subject?.topics?.length);
    document.getElementById('quizSyllabusPreviewPanel').hidden = true;
    document.getElementById('quizSyllabusStatus').textContent = error?.message || 'The syllabus could not be extracted. Choose another file or retry.';
    document.getElementById('quizSyllabusStatus').classList.add('quiz-status--error');
    document.getElementById('quizRemoveSyllabusBtn').hidden = false;
    document.getElementById('quizAvailableCount').textContent = 'Choose topic(s) to check the saved question bank';
    quizAvailability = null;
    resetQuizSelection('Upload failed. Select saved topics or retry with another file.');
    await refreshQuizAvailability();
  } finally {
    quizSyllabusFileInput.disabled = !document.getElementById('quizSubjectSelect').value;
    document.getElementById('quizRemoveSyllabusBtn').disabled = false;
    syllabusDropzone.setAttribute('aria-disabled', String(quizSyllabusFileInput.disabled));
    button.disabled = !pendingQuizSyllabusFile || !document.getElementById('quizSubjectSelect').value;
    button.textContent = 'Upload and extract';
    updateQuizSetupSummary();
  }
});

document.getElementById('quizRemoveSyllabusBtn').addEventListener('click', () => {
  activeQuizSyllabus = null;
  pendingQuizSyllabusFile = null;
  quizSyllabusFileInput.value = '';
  document.getElementById('quizSyllabusFileMeta').textContent = 'No file selected';
  document.getElementById('quizSyllabusStatus').textContent = 'Temporary syllabus selection removed. You can choose another file.';
  document.getElementById('quizSyllabusStatus').classList.remove('quiz-status--error');
  document.getElementById('quizSyllabusPreviewPanel').hidden = true;
  document.getElementById('quizRemoveSyllabusBtn').hidden = true;
  const subject = subjects.find(item => item.id === document.getElementById('quizSubjectSelect').value);
  renderQuizTopicCheckboxes(subject?.topics || []);
  document.getElementById('quizTopicSearch').disabled = !(subject?.topics?.length);
  document.getElementById('quizSelectAllTopics').disabled = !(subject?.topics?.length);
  document.getElementById('quizClearTopics').disabled = !(subject?.topics?.length);
  document.getElementById('quizUploadSyllabusBtn').disabled = true;
  resetQuizSelection('Syllabus selection cleared. Choose saved topics or upload another syllabus.');
  refreshQuizAvailability();
});

document.getElementById('quizSelectAllTopics').addEventListener('click', () => {
  document.querySelectorAll('#quizTopicCheckboxes input[type="checkbox"]').forEach(input => {
    input.checked = true;
    input.closest('.quiz-topic-option').classList.add('is-selected');
  });
  updateQuizSetupSummary();
  refreshQuizAvailability();
});

document.getElementById('quizClearTopics').addEventListener('click', () => {
  document.querySelectorAll('#quizTopicCheckboxes input[type="checkbox"]').forEach(input => {
    input.checked = false;
    input.closest('.quiz-topic-option').classList.remove('is-selected');
  });
  updateQuizSetupSummary();
  refreshQuizAvailability();
});

document.getElementById('quizTopicSearch').addEventListener('input', event => {
  const filter = event.target.value.trim().toLocaleLowerCase();
  document.querySelectorAll('#quizTopicCheckboxes .quiz-topic-option').forEach(label => {
    label.hidden = !label.textContent.toLocaleLowerCase().includes(filter);
  });
});

document.getElementById('quizQuestionCount').addEventListener('input', updateQuizSetupSummary);
document.getElementById('quizDifficulty').addEventListener('change', () => {
  updateQuizSetupSummary();
  refreshQuizAvailability();
});

document.getElementById('createBankQuizBtn').addEventListener('click', async () => {
  const subjectId = document.getElementById('quizSubjectSelect').value;
  const topicIds = selectedQuizTopicIds();
  const questionCount = Number(document.getElementById('quizQuestionCount').value);
  const difficulty = document.getElementById('quizDifficulty').value;
  if (!subjectId || !topicIds.length || !Number.isInteger(questionCount) || questionCount < 1 || questionCount > 20 || questionCount > quizAvailability) return;
  const button = document.getElementById('createBankQuizBtn');
  bankQuizCreating = true;
  button.disabled = true;
  document.getElementById('quizListStatus').textContent = 'Building a quiz from your saved questions…';
  try {
    const quiz = await Auth.apiFetch('/academics/quizzes/create/', {
      method: 'POST', throwOnError: true,
      body: JSON.stringify({ subject_id: subjectId, topic_ids: topicIds, question_count: questionCount, difficulty })
    });
    document.getElementById('quizListStatus').textContent = `Ready: ${quiz.questions.length} saved question(s), linked to your selected topics.`;
    await renderTopicQuiz(quiz);
  } catch (error) {
    document.getElementById('quizListStatus').textContent = error?.message || 'Could not create a quiz from the saved question bank.';
    await refreshQuizAvailability();
  } finally {
    bankQuizCreating = false;
    updateQuizSetupSummary();
  }
});

document.getElementById('loadTopicQuizzesBtn').addEventListener('click', async () => {
  const subjectId = document.getElementById('quizSubjectSelect').value;
  const topicIds = selectedQuizTopicIds();
  if (!subjectId || !topicIds.length) return;
  savedQuizLoading = true;
  updateQuizSetupSummary();
  const loadButton = document.getElementById('loadTopicQuizzesBtn');
  const oldText = loadButton.textContent;
  loadButton.textContent = 'Loading saved quizzes…';
  const statusEl = document.getElementById('quizListStatus');
  statusEl.textContent = 'Loading saved quizzes…';
  document.getElementById('topicQuizList').replaceChildren();
  document.getElementById('topicQuizDetail').replaceChildren();
  document.getElementById('quizAttemptHistory').replaceChildren();
  try {
    const results = await Promise.all(topicIds.map(topicId => {
      const query = new URLSearchParams({ subject_id: subjectId, topic_id: topicId });
      if (activeQuizSyllabus?.token) query.set('upload_token', activeQuizSyllabus.token);
      return Auth.apiFetch(`/academics/quizzes/?${query}`);
    }));
    const quizzes = [...new Map(results.flat().filter(Boolean).map(quiz => [quiz.id, quiz])).values()];
    if (results.some(result => !result)) throw new Error('Could not load saved quizzes. Please try again.');
    if (!quizzes.length) {
      statusEl.textContent = 'No saved quizzes exist for these topics yet. Use the question bank or generate questions from the syllabus.';
      return;
    }
    statusEl.textContent = `${quizzes.length} saved quiz${quizzes.length === 1 ? '' : 'zes'} found.`;
    quizzes.forEach(quiz => {
      const card = document.createElement('article');
      card.className = 'topic-quiz-card';
      const title = document.createElement('h3');
      title.textContent = quiz.title;
      const details = document.createElement('p');
      const sourceLabel = quiz.source === 'openai_generated' ? 'AI generated from syllabus' : (quiz.source === 'question_bank' ? 'Question bank' : 'Curated');
      details.textContent = `${quiz.subject_name} · ${quiz.topic_name} · ${quiz.question_count} question(s) · ${sourceLabel}`;
      const button = document.createElement('button');
      button.className = 'btn btn-primary btn-sm';
      button.type = 'button';
      button.textContent = 'Start quiz';
      button.addEventListener('click', () => loadTopicQuiz(quiz.id));
      card.append(title, details, button);
      document.getElementById('topicQuizList').appendChild(card);
    });
  } catch (error) {
    statusEl.textContent = error?.message || 'Could not load saved quizzes.';
  } finally {
    savedQuizLoading = false;
    loadButton.textContent = oldText;
    updateQuizSetupSummary();
  }
});

document.getElementById('generateTopicQuizBtn').addEventListener('click', async () => {
  if (!AI_QUIZ_GENERATION_ENABLED) return;
  const subjectId = document.getElementById('quizSubjectSelect').value;
  const topicIds = selectedQuizTopicIds();
  const count = Number(document.getElementById('quizQuestionCount').value);
  if (!subjectId || !activeQuizSyllabus?.token || !topicIds.length || !Number.isInteger(count) || count < 1 || count > 20) return;
  const button = document.getElementById('generateTopicQuizBtn');
  syllabusQuizGenerating = true;
  button.disabled = true;
  document.getElementById('quizListStatus').textContent = 'Generating questions from your uploaded syllabus…';
  try {
    const quiz = await Auth.apiFetch('/academics/quizzes/generate/', {
      method: 'POST', throwOnError: true,
      body: JSON.stringify({
        subject_id: subjectId, topic_ids: topicIds, question_count: count,
        difficulty: document.getElementById('quizDifficulty').value,
        syllabus_token: activeQuizSyllabus.token,
      })
    });
    document.getElementById('quizListStatus').textContent = `Generated and saved ${quiz.questions.length} syllabus question(s).`;
    await renderTopicQuiz(quiz);
  } catch (error) {
    document.getElementById('quizListStatus').textContent = error?.message || 'Syllabus question generation is unavailable.';
  } finally {
    syllabusQuizGenerating = false;
    updateQuizSetupSummary();
  }
});

async function loadTopicQuiz(quizId) {
  const detail = document.getElementById('topicQuizDetail');
  detail.replaceChildren();
  document.getElementById('quizAttemptHistory').replaceChildren();
  const loading = document.createElement('p');
  loading.className = 'quiz-status';
  loading.textContent = 'Loading quiz questions…';
  detail.appendChild(loading);
  const quiz = await Auth.apiFetch(`/academics/quizzes/${encodeURIComponent(quizId)}/`);
  detail.replaceChildren();
  if (!quiz) {
    const error = document.createElement('p');
    error.className = 'quiz-status quiz-status--error';
    error.textContent = 'Could not load this quiz. It may have been removed; please reload the quiz list.';
    detail.appendChild(error);
    return;
  }
  await renderTopicQuiz(quiz);
}

async function renderTopicQuiz(quiz) {
  const detail = document.getElementById('topicQuizDetail');
  detail.replaceChildren();
  currentTopicQuiz = quiz;
  quizQuestionIndex = 0;
  quizAnswers = {};
  quizSubmitting = false;
  const header = document.createElement('div');
  header.className = 'quiz-detail-header';
  const title = document.createElement('h2');
  title.textContent = quiz.title;
  const context = document.createElement('p');
  const sourceLabel = quiz.source === 'openai_generated' ? 'AI generated from syllabus' : (quiz.source === 'question_bank' ? 'Saved question bank' : 'Curated');
  context.textContent = `${quiz.subject_name} · ${quiz.topic_name} · ${quiz.questions.length} question(s) · ${quiz.difficulty || 'medium'} · ${sourceLabel}`;
  header.append(title, context);
  detail.appendChild(header);

  const form = document.createElement('form');
  form.className = 'quiz-question-form';
  const progress = document.createElement('p');
  progress.className = 'quiz-progress';
  progress.setAttribute('aria-live', 'polite');
  quiz.questions.forEach((question, index) => {
    const fieldset = document.createElement('fieldset');
    fieldset.className = 'quiz-question';
    fieldset.hidden = index !== 0;
    const legend = document.createElement('legend');
    legend.textContent = `${index + 1}. ${question.text}`;
    fieldset.appendChild(legend);
    question.options.forEach((optionText, optionIndex) => {
      const label = document.createElement('label');
      label.className = 'quiz-option';
      const input = document.createElement('input');
      input.type = 'radio';
      input.name = `question-${question.question_id}`;
      input.value = String(optionIndex);
      input.dataset.questionId = question.question_id;
      input.addEventListener('change', () => {
        quizAnswers[question.question_id] = optionIndex;
        next.disabled = false;
        if (quizQuestionIndex === quiz.questions.length - 1) submit.disabled = false;
      });
      const text = document.createElement('span');
      text.textContent = optionText;
      label.append(input, text);
      fieldset.appendChild(label);
    });
    form.appendChild(fieldset);
  });
  const navigation = document.createElement('div');
  navigation.className = 'quiz-navigation';
  const previous = document.createElement('button');
  previous.type = 'button';
  previous.className = 'btn btn-ghost';
  previous.textContent = 'Previous';
  previous.disabled = true;
  const next = document.createElement('button');
  next.type = 'button';
  next.className = 'btn btn-primary';
  next.textContent = quiz.questions.length > 1 ? 'Next question' : 'Review answers';
  next.disabled = true;
  const submit = document.createElement('button');
  submit.type = 'submit';
  submit.className = 'btn btn-primary';
  submit.textContent = 'Submit answers';
  submit.hidden = true;
  navigation.append(previous, next, submit);
  form.prepend(progress);
  form.appendChild(navigation);
  const updateQuestion = () => {
    form.querySelectorAll('.quiz-question').forEach((fieldset, index) => { fieldset.hidden = index !== quizQuestionIndex; });
    progress.textContent = `Question ${quizQuestionIndex + 1} of ${quiz.questions.length}`;
    previous.disabled = quizQuestionIndex === 0;
    const isLast = quizQuestionIndex === quiz.questions.length - 1;
    next.hidden = isLast;
    submit.hidden = !isLast;
    next.disabled = quizAnswers[quiz.questions[quizQuestionIndex].question_id] === undefined;
    submit.disabled = quizAnswers[quiz.questions[quizQuestionIndex].question_id] === undefined;
  };
  previous.addEventListener('click', () => {
    if (quizQuestionIndex > 0) { quizQuestionIndex -= 1; updateQuestion(); }
  });
  next.addEventListener('click', () => {
    if (quizAnswers[quiz.questions[quizQuestionIndex].question_id] === undefined) return;
    if (quizQuestionIndex < quiz.questions.length - 1) quizQuestionIndex += 1;
    updateQuestion();
  });
  updateQuestion();
  form.addEventListener('submit', submitTopicQuiz);
  detail.appendChild(form);

  const historyButton = document.createElement('button');
  historyButton.type = 'button';
  historyButton.className = 'btn btn-ghost btn-sm quiz-history-button';
  historyButton.textContent = 'View attempt history';
  historyButton.addEventListener('click', () => loadQuizAttemptHistory(quiz.id));
  detail.appendChild(historyButton);
}

async function submitTopicQuiz(event) {
  event.preventDefault();
  if (!currentTopicQuiz || quizSubmitting) return;
  const form = event.currentTarget;
  const submit = form.querySelector('button[type="submit"]');
  const answers = currentTopicQuiz.questions.map(question => ({
    question_id: question.question_id, selected_index: quizAnswers[question.question_id],
  }));
  if (answers.some(answer => !Number.isInteger(answer.selected_index))) return;
  if (!window.confirm('Submit your answers and see your result?')) return;
  quizSubmitting = true;
  submit.disabled = true;
  submit.textContent = 'Submitting…';
  const result = await Auth.apiFetch(`/academics/quizzes/${encodeURIComponent(currentTopicQuiz.id)}/attempts/`, {
    method: 'POST',
    body: JSON.stringify({ answers })
  });
  submit.disabled = false;
  submit.textContent = 'Submit answers';
  if (!result) {
    quizSubmitting = false;
    submit.disabled = false;
    showToast('Quiz submission failed. Please try again.', 'error');
    return;
  }
  renderQuizAttemptResult(result, document.getElementById('topicQuizDetail'));
  showToast('Quiz submitted and result saved.');
  await loadQuizAttemptHistory(currentTopicQuiz.id);
}

function renderQuizAttemptResult(attempt, parent) {
  const panel = document.createElement('section');
  panel.className = 'quiz-result-panel';
  const heading = document.createElement('h3');
  heading.textContent = `Result: ${attempt.score}% (${attempt.correct_count}/${attempt.total_questions} correct)`;
  const counts = document.createElement('p');
  counts.textContent = `${attempt.incorrect_count} incorrect · ${formatDateTime(attempt.created_at)}`;
  panel.append(heading, counts);
  attempt.answers.forEach((answer, index) => {
    const item = document.createElement('article');
    item.className = `quiz-answer-review ${answer.is_correct ? 'quiz-answer-review--correct' : 'quiz-answer-review--incorrect'}`;
    const question = document.createElement('h4');
    question.textContent = `${index + 1}. ${answer.question}`;
    const status = document.createElement('p');
    status.textContent = answer.is_correct ? 'Correct' : `Incorrect · Your answer: ${answer.selected_answer}`;
    const correct = document.createElement('p');
    correct.textContent = `Correct answer: ${answer.correct_answer}`;
    item.append(question, status, correct);
    if (answer.explanation) {
      const explanation = document.createElement('p');
      explanation.textContent = answer.explanation;
      item.appendChild(explanation);
    }
    panel.appendChild(item);
  });
  const retry = document.createElement('button');
  retry.type = 'button';
  retry.className = 'btn btn-ghost';
  retry.textContent = 'Retry quiz';
  retry.addEventListener('click', () => loadTopicQuiz(attempt.quiz_id));
  panel.appendChild(retry);
  parent.appendChild(panel);
}

function formatDateTime(value) {
  if (!value) return 'Date unavailable';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? 'Date unavailable' : parsed.toLocaleString();
}

async function loadQuizAttemptHistory(quizId) {
  const history = document.getElementById('quizAttemptHistory');
  history.replaceChildren();
  const status = document.createElement('p');
  status.className = 'quiz-status';
  status.textContent = 'Loading attempt history…';
  history.appendChild(status);
  const attempts = await Auth.apiFetch(`/academics/quizzes/${encodeURIComponent(quizId)}/attempts/`);
  history.replaceChildren();
  const heading = document.createElement('h3');
  heading.textContent = 'Your attempts';
  history.appendChild(heading);
  if (!attempts) {
    const error = document.createElement('p');
    error.className = 'quiz-status quiz-status--error';
    error.textContent = 'Could not load your attempt history.';
    history.appendChild(error);
  } else if (!attempts.length) {
    const empty = document.createElement('p');
    empty.className = 'quiz-status';
    empty.textContent = 'No attempts yet. Complete this quiz to see your result here.';
    history.appendChild(empty);
  } else {
    attempts.forEach(attempt => {
      const row = document.createElement('article');
      row.className = 'quiz-history-row';
      const summary = document.createElement('p');
      summary.textContent = `${attempt.score}% · ${attempt.correct_count}/${attempt.total_questions} correct · ${formatDateTime(attempt.created_at)}`;
      const resultButton = document.createElement('button');
      resultButton.type = 'button';
      resultButton.className = 'btn btn-ghost btn-sm';
      resultButton.textContent = 'Review result';
      resultButton.addEventListener('click', () => renderQuizAttemptResult(attempt, history));
      row.append(summary, resultButton);
      history.appendChild(row);
    });
  }
}

/* ===== FETCH ALL DATA ===== */
async function loadAll() {
  [subjects, assignments, exams, studyPlans] = await Promise.all([
    Auth.apiFetch('/academics/subjects/'),
    Auth.apiFetch('/academics/assignments/'),
    Auth.apiFetch('/academics/exams/'),
    Auth.apiFetch('/academics/study-plans/')
  ]);
  subjects = subjects || [];
  assignments = assignments || [];
  exams = exams || [];
  studyPlans = studyPlans || [];

  populateSubjectSelects();
  fillQuizSubjectSelect();
  renderStats();
  renderOverviewLists();
  renderInsights();
  renderSubjects();
  renderAssignments();
  renderExams();
  renderStudyPlans();
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

  // Remaining study sessions across all saved plans
  const allSessions = studyPlans.flatMap(p => p.sessions || []);
  const remainingSessions = allSessions.filter(s => !s.is_completed).length;
  const completedSessions = allSessions.length - remainingSessions;
  const sessionPct = allSessions.length ? Math.round((completedSessions / allSessions.length) * 100) : 0;

  const el = document.getElementById('studyProgressSummary');
  if (el) {
    if (!allSessions.length) {
      el.innerHTML = `<div class="dash-empty" style="padding:12px 0">No study sessions yet.</div>`;
    } else {
      el.innerHTML = `
        <div style="display:flex;justify-content:space-between;font-size:0.75rem;color:var(--muted);margin-bottom:6px">
          <span>${completedSessions} of ${allSessions.length} sessions complete</span>
          <span>${sessionPct}%</span>
        </div>
        <div class="progress-bar-wrap"><div class="progress-bar" style="width:${sessionPct}%"></div></div>
        <div style="margin-top:8px;font-size:0.75rem;color:var(--muted)">${remainingSessions} session(s) remaining</div>`;
    }
  }
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
            <div class="topic-check ${t.is_completed ? 'done' : ''}" onclick="toggleTopic('${t.id}', ${!t.is_completed})"></div>
            <span class="topic-name ${t.is_completed ? 'done' : ''}">${t.title}</span>
            <span class="difficulty-badge difficulty-${t.difficulty || 'medium'}">${t.difficulty || 'medium'}</span>
            ${t.status === 'in_progress' ? '<span class="difficulty-badge" style="background:rgba(56,189,248,0.12);color:#38bdf8">In Progress</span>' : ''}
            ${t.revision_required ? '<span class="difficulty-badge" style="background:rgba(251,191,36,0.14);color:#fbbf24">Revision</span>' : ''}
            <button class="icon-btn" onclick="openEditTopic('${t.id}', '${t.title.replace(/'/g, "\\'").replace(/"/g, '&quot;')}', '${t.difficulty || 'medium'}', '${t.status || (t.is_completed ? 'completed' : 'not_started')}', ${t.revision_required === true})" title="Edit topic">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
            </button>
            <button class="icon-btn danger" onclick="deleteTopic('${t.id}')" title="Delete topic">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none"><path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
            </button>
          </div>`).join('')}
      </div>` : ''}
      ${(s.syllabus_files && s.syllabus_files.length) ? `<div class="syllabus-files-section">
        <div class="syllabus-files-label">Syllabus Files</div>
        ${s.syllabus_files.map(f => `<div class="syllabus-file-item">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" stroke="currentColor" stroke-width="2"/><polyline points="14 2 14 8 20 8" stroke="currentColor" stroke-width="2"/></svg>
          <span>${f.name}</span>
          <button class="icon-btn danger" onclick="deleteSyllabusFile('${s.id}', '${f.filename}')" title="Remove file">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none"><path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
          </button>
        </div>`).join('')}
      </div>` : ''}
      <div class="subject-card-actions">
        <button class="btn btn-ghost" onclick="openAddTopic('${s.id}')">+ Topic</button>
        <button class="btn btn-ghost" onclick="openUploadSyllabus('${s.id}')">+ File</button>
        <button class="btn btn-ghost" onclick="openEditSubject('${s.id}')">Edit</button>
        <button class="btn btn-ghost" style="color:#f87171" onclick="deleteSubject('${s.id}')">Delete</button>
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
            <button class="icon-btn" onclick="toggleAssignment('${a.id}', ${!a.is_completed})" title="${a.is_completed ? 'Mark pending' : 'Mark done'}">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none"><path d="M20 6L9 17l-5-5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
            </button>
            <button class="icon-btn" onclick="openEditAssignment('${a.id}')" title="Edit">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
            </button>
            <button class="icon-btn danger" onclick="deleteAssignment('${a.id}')" title="Delete">
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
        <button class="icon-btn" onclick="openEditExam('${e.id}')" title="Edit">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
        </button>
        <button class="icon-btn danger" onclick="deleteExam('${e.id}')" title="Delete">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none"><polyline points="3 6 5 6 21 6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M19 6l-1 14H6L5 6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M10 11v6M14 11v6M9 6V4h6v2" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
        </button>
      </div>
    </div>`;
  }).join('');
}

/* ===== SUBJECT CRUD ===== */
document.getElementById('addSubjectBtn').addEventListener('click', () => {
  currentUploadSubjectId = null;
  document.getElementById('subjectModalTitle').textContent = 'Add Subject';
  document.getElementById('subjectId').value = '';
  document.getElementById('subjectName').value = '';
  document.getElementById('subjectDesc').value = '';
  const filesGroup = document.getElementById('subjectFilesGroup');
  if (filesGroup) filesGroup.style.display = 'none';
  const fileInput = document.getElementById('syllabusFileInput');
  if (fileInput) fileInput.value = '';
  const filesList = document.getElementById('subjectFilesList');
  if (filesList) filesList.innerHTML = '';
  openModal('subjectModal');
});

function openEditSubject(id) {
  const s = subjects.find(x => x.id === id);
  if (!s) return;
  currentUploadSubjectId = s.id;
  document.getElementById('subjectModalTitle').textContent = 'Edit Subject';
  document.getElementById('subjectId').value = s.id;
  document.getElementById('subjectName').value = s.name;
  document.getElementById('subjectDesc').value = s.description || '';
  const filesGroup = document.getElementById('subjectFilesGroup');
  if (filesGroup) {
    filesGroup.style.display = 'block';
    renderSubjectModalFiles(s);
  }
  const fileInput = document.getElementById('syllabusFileInput');
  if (fileInput) fileInput.value = '';
  openModal('subjectModal');
}

function renderSubjectModalFiles(subject) {
  const el = document.getElementById('subjectFilesList');
  if (!el) return;
  const files = subject?.syllabus_files || [];
  if (!files.length) {
    el.innerHTML = '<div style="color:var(--muted);font-size:0.75rem;padding:4px 0">No syllabus files uploaded yet.</div>';
    return;
  }
  el.innerHTML = files.map(f => `
    <div class="syllabus-file-item">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" stroke="currentColor" stroke-width="2"/><polyline points="14 2 14 8 20 8" stroke="currentColor" stroke-width="2"/></svg>
      <span>${f.name}</span>
      <button type="button" class="icon-btn danger" onclick="deleteSyllabusFile('${subject.id}', '${f.filename}')" title="Remove file">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none"><path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
      </button>
    </div>`).join('');
}

document.getElementById('subjectForm').addEventListener('submit', async e => {
  e.preventDefault();
  const id = document.getElementById('subjectId').value;
  const name = document.getElementById('subjectName').value.trim();
  if (!name) return;
  const body = { name, description: document.getElementById('subjectDesc').value.trim() };
  const res = id
    ? await Auth.apiFetch(`/academics/subjects/${id}/`, { method: 'PUT', body: JSON.stringify(body) })
    : await Auth.apiFetch('/academics/subjects/', { method: 'POST', body: JSON.stringify(body) });
  if (res !== null) {
    const subjectId = id || res.id;
    const fileInput = document.getElementById('syllabusFileInput');
    const pendingFile = fileInput?.files?.[0];
    if (pendingFile && subjectId) {
      fileInput.value = '';
      closeModal('subjectModal');
      await uploadSyllabusFile(subjectId, pendingFile);
    } else {
      closeModal('subjectModal');
      showToast(id ? 'Subject updated!' : 'Subject added!');
      await loadAll();
    }
  } else showToast('Something went wrong. Check the browser console for details.', 'error');
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
    subject: document.getElementById('topicSubjectId').value,
    title: document.getElementById('topicTitle').value.trim(),
    difficulty: document.getElementById('topicDifficulty').value,
  };
  const res = await Auth.apiFetch('/academics/topics/', { method: 'POST', body: JSON.stringify(body) });
  if (res) { closeModal('topicModal'); showToast('Topic added!'); await loadAll(); }
  else showToast('Something went wrong.', 'error');
});

async function toggleTopic(id, completed) {
  await Auth.apiFetch(`/academics/topics/${id}/`, { method: 'PATCH', body: JSON.stringify({ is_completed: completed }) });
  await loadAll();
}

function openEditTopic(id, title, difficulty, topicStatus, revisionRequired) {
  document.getElementById('editTopicId').value = id;
  document.getElementById('editTopicTitle').value = title;
  document.getElementById('editTopicDifficulty').value = difficulty;
  document.getElementById('editTopicStatus').value = topicStatus || 'not_started';
  document.getElementById('editTopicRevisionRequired').checked = revisionRequired === true;
  openModal('editTopicModal');
}

document.getElementById('editTopicForm').addEventListener('submit', async e => {
  e.preventDefault();
  const id = document.getElementById('editTopicId').value;
  const body = {
    title: document.getElementById('editTopicTitle').value.trim(),
    difficulty: document.getElementById('editTopicDifficulty').value,
    status: document.getElementById('editTopicStatus').value,
    revision_required: document.getElementById('editTopicRevisionRequired').checked,
  };
  const res = await Auth.apiFetch(`/academics/topics/${id}/`, { method: 'PATCH', body: JSON.stringify(body) });
  if (res) { closeModal('editTopicModal'); showToast('Topic updated!'); await loadAll(); }
  else showToast('Something went wrong.', 'error');
});

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
    subject: subVal || null,
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
    subject: subVal || null,
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

/* ===== SYLLABUS FILE UPLOAD + EXTRACT ===== */
let currentUploadSubjectId = null;
let syllabusReviewState = null;  // { subjectId, filename, topics }

function openUploadSyllabus(subjectId) {
  currentUploadSubjectId = subjectId;
  const fileInput = document.getElementById('syllabusFileInput');
  if (fileInput) {
    fileInput.value = '';
    fileInput.click();
  } else {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.pdf,.docx,.txt,.pptx';
    input.onchange = async () => {
      const file = input.files?.[0];
      if (file) await uploadSyllabusFile(subjectId, file);
    };
    input.click();
  }
}

async function uploadSyllabusFile(subjectId, file) {
  if (!file) return;
  console.log(`[Syllabus] Initiating upload: "${file.name}" (${file.size} bytes) for subject ID "${subjectId}"`);

  const allowed = ['.pdf', '.docx', '.txt', '.pptx'];
  const ext = '.' + file.name.split('.').pop().toLowerCase();
  if (!allowed.includes(ext)) {
    const msg = `Unsupported file type "${ext}". Allowed: PDF, DOCX, TXT, PPTX`;
    console.error(`[Syllabus] ${msg}`);
    showToast(msg, 'error');
    return;
  }

  const formData = new FormData();
  formData.append('file', file);
  showToast('Uploading syllabus file…');

  let res, data;
  try {
    res = await fetch(`${API}/academics/subjects/${subjectId}/files/`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${Auth.getToken()}` },
      body: formData
    });
    data = await res.json().catch(() => ({}));
  } catch (netErr) {
    console.error('[Syllabus] Network error during upload request:', netErr);
    showToast('Network error: could not connect to server.', 'error');
    return;
  }

  if (!res.ok) {
    const errorMsg = data?.detail || `Upload failed (HTTP ${res.status}).`;
    console.error(`[Syllabus] Upload failed (HTTP ${res.status}):`, errorMsg);
    showToast(errorMsg, 'error');
    return;
  }

  console.log('[Syllabus] Upload successful, server response:', data);
  showToast('File uploaded! Extracting topics…');

  const uploaded = (data.syllabus_files && data.syllabus_files[data.syllabus_files.length - 1]);
  await loadAll();

  // If the subject modal is currently open, refresh its syllabus file list
  const currentSub = subjects.find(s => s.id === subjectId);
  if (currentSub) renderSubjectModalFiles(currentSub);

  if (uploaded?.filename) {
    await openSyllabusReview(subjectId, uploaded.filename, uploaded.name);
  } else {
    console.warn('[Syllabus] Uploaded file entry missing from response');
  }
}

const syllabusFileInput = document.getElementById('syllabusFileInput');
if (syllabusFileInput) {
  syllabusFileInput.addEventListener('change', async e => {
    const file = e.target.files?.[0];
    if (!file) return;
    const subjectId = currentUploadSubjectId || document.getElementById('subjectId').value;
    if (!subjectId) {
      console.warn('[Syllabus] File selected but no subject is active.');
      showToast('Please select or save a subject first.', 'error');
      return;
    }
    await uploadSyllabusFile(subjectId, file);
    e.target.value = '';
  });
}

async function openSyllabusReview(subjectId, filename, displayName) {
  console.log(`[Syllabus] Extraction API request: subject=${subjectId}, file=${filename}`);
  let res, data;
  try {
    res = await fetch(
      `${API}/academics/subjects/${subjectId}/files/${encodeURIComponent(filename)}/extract/`,
      { method: 'POST', headers: { Authorization: `Bearer ${Auth.getToken()}` } }
    );
    data = await res.json().catch(() => null);
  } catch (netErr) {
    console.error('[Syllabus] Network error during extraction request:', netErr);
    showToast('Network error: could not connect to server.', 'error');
    return;
  }

  if (!res.ok || !data) {
    const errDetail = data?.detail || 'Could not extract topics from file.';
    console.error(`[Syllabus] Extraction failed:`, errDetail);
    showToast(errDetail, 'error');
    return;
  }

  console.log(`[Syllabus] Extraction successful: ${data.total_found} topic(s) found`, data.topics);
  syllabusReviewState = { subjectId, filename, topics: data.topics || [] };

  document.getElementById('syllabusReviewMeta').textContent =
    `${displayName || filename} · ${data.total_found} topic(s) found · ${data.existing_topic_count} already in subject`;

  const warnEl = document.getElementById('syllabusReviewWarning');
  if (data.warning) {
    warnEl.textContent = '⚠ ' + data.warning;
    warnEl.style.display = 'block';
  } else {
    warnEl.style.display = 'none';
  }

  renderSyllabusTopicsList(data.topics || []);
  openModal('syllabusReviewModal');
}

function renderSyllabusTopicsList(topics) {
  const el = document.getElementById('syllabusTopicsList');
  if (!topics.length) {
    el.innerHTML = `<div class="dash-empty">No topics could be extracted from this file.</div>`;
    return;
  }
  el.innerHTML = topics.map((t, i) => `
    <div class="syllabus-review-item ${t.is_duplicate ? 'review-duplicate' : ''}">
      <input type="checkbox" class="syllabus-topic-check" data-index="${i}" ${t.is_duplicate ? '' : 'checked'}
        style="cursor:pointer;flex-shrink:0" />
      <div style="flex:1;min-width:0">
        <input type="text" class="syllabus-topic-title form-input" data-index="${i}"
          value="${(t.title || '').replace(/"/g, '&quot;')}"
          style="height:32px;padding:0 10px;font-size:0.82rem;width:100%" />
        ${t.unit ? `<div style="color:var(--muted);font-size:0.68rem;margin-top:2px">${t.unit}</div>` : ''}
      </div>
      <select class="syllabus-topic-diff form-input form-select" data-index="${i}"
        style="height:32px;padding:0 8px;font-size:0.75rem;width:80px;flex-shrink:0">
        <option value="easy">Easy</option>
        <option value="medium" selected>Medium</option>
        <option value="hard">Hard</option>
      </select>
      ${t.is_duplicate ? '<span style="color:#fbbf24;font-size:0.65rem;white-space:nowrap">duplicate</span>' : ''}
    </div>`).join('');
}

document.getElementById('syllabusSelectAll').addEventListener('click', () => {
  const checks = document.querySelectorAll('.syllabus-topic-check');
  const allChecked = [...checks].every(c => c.checked);
  checks.forEach(c => c.checked = !allChecked);
  document.getElementById('syllabusSelectAll').textContent = allChecked ? 'Select All' : 'Deselect All';
});

document.getElementById('syllabusImportBtn').addEventListener('click', async () => {
  if (!syllabusReviewState) return;
  const { subjectId } = syllabusReviewState;
  const skipDupes = document.getElementById('syllabusSkipDupes').checked;

  const checks = document.querySelectorAll('.syllabus-topic-check');
  const titles = document.querySelectorAll('.syllabus-topic-title');
  const diffs = document.querySelectorAll('.syllabus-topic-diff');

  const selected = [];
  checks.forEach((c, i) => {
    if (c.checked) {
      const tVal = titles[i].value.trim();
      if (tVal) {
        selected.push({
          title: tVal,
          difficulty: diffs[i].value,
        });
      }
    }
  });

  if (!selected.length) { showToast('No topics selected.', 'error'); return; }

  console.log(`[Syllabus] Importing ${selected.length} topic(s) to subject "${subjectId}" (skip_duplicates=${skipDupes})`);
  const res = await Auth.apiFetch(`/academics/subjects/${subjectId}/topics/import/`, {
    method: 'POST',
    body: JSON.stringify({ topics: selected, skip_duplicates: skipDupes })
  });

  if (res) {
    console.log('[Syllabus] Import API successful:', res);
    closeModal('syllabusReviewModal');
    showToast(`Imported ${res.added} topic(s)${res.skipped ? `, skipped ${res.skipped} duplicate(s)` : ''}.`);
    syllabusReviewState = null;
    await loadAll();
    const currentSub = subjects.find(s => s.id === subjectId);
    if (currentSub) renderSubjectModalFiles(currentSub);
  } else {
    console.error('[Syllabus] Topic import API request failed');
    showToast('Import failed.', 'error');
  }
});

async function deleteSyllabusFile(subjectId, filename) {
  if (!confirm('Remove this file?')) return;
  console.log(`[Syllabus] Deleting file: subject=${subjectId}, file=${filename}`);
  let res;
  try {
    res = await fetch(`${API}/academics/subjects/${subjectId}/files/${encodeURIComponent(filename)}/`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${Auth.getToken()}` }
    });
  } catch (err) {
    console.error('[Syllabus] Network error during file deletion:', err);
    showToast('Network error while deleting file.', 'error');
    return;
  }
  if (res.ok) {
    showToast('File removed.');
    await loadAll();
    const currentSub = subjects.find(s => s.id === subjectId);
    if (currentSub) renderSubjectModalFiles(currentSub);
  } else {
    console.error('[Syllabus] Failed to remove file, status:', res.status);
    showToast('Failed to remove file.', 'error');
  }
}

/* ===== STUDY PLAN ===== */
function renderStudyPlans() {
  const el = document.getElementById('studyPlansList');
  if (!studyPlans.length) {
    el.innerHTML = `<div class="dash-empty">No saved study plans yet. Click "Generate Plan" to create one!</div>`;
    return;
  }
  el.innerHTML = studyPlans.map(p => {
    const total = (p.sessions || []).length;
    const done = (p.sessions || []).filter(s => s.is_completed).length;
    const pct = total ? Math.round((done / total) * 100) : 0;

    const sessionsByDate = {};
    (p.sessions || []).forEach(s => {
      if (!sessionsByDate[s.date]) sessionsByDate[s.date] = [];
      sessionsByDate[s.date].push(s);
    });
    const dates = Object.keys(sessionsByDate).sort();

    return `<div class="dash-card study-plan-card" style="margin-bottom:16px">
      <div class="dash-card-header">
        <div>
          <span class="dash-card-title">${p.title}</span>
          <div style="color:var(--muted);font-size:0.72rem;margin-top:2px">${formatDate(p.start_date)} → ${formatDate(p.end_date)} · ${p.daily_hours}h/day</div>
        </div>
        <div style="display:flex;gap:6px">
          <button class="btn btn-ghost btn-sm" onclick="openReschedule('${p.id}', '${p.daily_hours}')" title="Reschedule">↺ Reschedule</button>
          <button class="icon-btn danger" onclick="deleteStudyPlan('${p.id}')" title="Delete plan">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none"><polyline points="3 6 5 6 21 6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M19 6l-1 14H6L5 6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M10 11v6M14 11v6M9 6V4h6v2" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
          </button>
        </div>
      </div>
      <div style="margin:8px 0 12px">
        <div style="display:flex;justify-content:space-between;font-size:0.75rem;color:var(--muted);margin-bottom:4px">
          <span>Progress: ${done}/${total} sessions</span>
          <span>${pct}%</span>
        </div>
        <div class="progress-bar-wrap">
          <div class="progress-bar" style="width:${pct}%"></div>
        </div>
      </div>
      <div class="study-sessions-list">
        ${dates.map(date => `
          <div class="study-day-group">
            <div class="study-day-label">${formatDate(date)}</div>
            ${sessionsByDate[date].map(s => `
              <div class="study-session-item ${s.is_completed ? 'session-done' : ''}">
                <input type="checkbox" ${s.is_completed ? 'checked' : ''}
                  ${s.session_id ? `onchange="toggleSession('${p.id}', '${s.session_id}', this.checked, this)"` : 'disabled title="Session ID missing — please delete and regenerate this plan"'}
                  style="cursor:${s.session_id ? 'pointer' : 'not-allowed'};margin-right:6px" />
                <span class="session-subject-tag">${s.subject}</span>
                <span class="session-topic-name">${s.topic}</span>
                <span class="session-dur">${s.duration}</span>
              </div>`).join('')}
          </div>`).join('')}
      </div>
    </div>`;
  }).join('');
}

document.getElementById('generatePlanBtn').addEventListener('click', () => {
  document.getElementById('planTitle').value = '';
  document.getElementById('planStartDate').value = '';
  document.getElementById('planEndDate').value = '';
  document.getElementById('planDailyHours').value = '2';

  // Render exam checkboxes
  const examBox = document.getElementById('planExamCheckboxes');
  const upcomingExams = exams.filter(e => daysUntil(e.exam_date) >= 0).sort((a, b) => new Date(a.exam_date) - new Date(b.exam_date));
  examBox.innerHTML = upcomingExams.length
    ? upcomingExams.map(e => `
        <label style="display:flex;align-items:center;gap:8px;cursor:pointer;font-size:0.82rem;color:var(--text)">
          <input type="checkbox" class="plan-exam-cb" value="${e.id}" style="cursor:pointer" />
          <span>${e.title} <span style="color:var(--muted);font-size:0.72rem">(${formatDate(e.exam_date)})</span></span>
        </label>`).join('')
    : '<span style="color:var(--muted);font-size:0.78rem">No upcoming exams</span>';

  // Render subject checkboxes
  const subBox = document.getElementById('planSubjectCheckboxes');
  subBox.innerHTML = subjects.length
    ? subjects.map(s => `
        <label style="display:flex;align-items:center;gap:8px;cursor:pointer;font-size:0.82rem;color:var(--text)">
          <input type="checkbox" class="plan-subject-cb" value="${s.id}" style="cursor:pointer" />
          <span>${s.name}</span>
        </label>`).join('')
    : '<span style="color:var(--muted);font-size:0.78rem">No subjects</span>';

  openModal('generatePlanModal');
});

document.getElementById('generatePlanForm').addEventListener('submit', async e => {
  e.preventDefault();
  const title = document.getElementById('planTitle').value.trim();
  const start_date = document.getElementById('planStartDate').value;
  const end_date = document.getElementById('planEndDate').value;
  const daily_hours = document.getElementById('planDailyHours').value;

  const selectedExams = [...document.querySelectorAll('.plan-exam-cb:checked')].map(c => c.value);
  const selectedSubjects = [...document.querySelectorAll('.plan-subject-cb:checked')].map(c => c.value);
  let res, rawStatus;

  const payload = {
    start_date,
    end_date,
    daily_hours,
    exam_ids: selectedExams,
    subject_ids: selectedSubjects,
  };

  let raw;
  try {
    raw = await fetch('http://127.0.0.1:8000/api/academics/study-plans/generate/', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${Auth.getToken()}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
  } catch (networkErr) {
    showToast('Network error — could not reach the server.', 'error');
    return;
  }

  rawStatus = raw.status;
  let body;
  try { body = await raw.json(); } catch (_) { body = null; }

  if (!raw.ok) {
    const detail = body?.detail || body?.message || `Server error (HTTP ${rawStatus}).`;
    showToast(detail, 'error');
    return;
  }

  res = body;

  if (!res || !Array.isArray(res.sessions)) {
    showToast('Unexpected response from server.', 'error');
    return;
  }

  if (res.sessions.length === 0) {
    showToast(res.message || 'No incomplete topics found for the selected subjects.', 'error');
    return;
  }

  generatedSessions = res.sessions;
  generatedPlanMeta = { title, start_date, end_date, daily_hours };

  closeModal('generatePlanModal');

  // Show generated plan preview
  const wrap = document.getElementById('generatedPlanWrap');
  document.getElementById('generatedPlanTitle').textContent = title;
  const sessionsEl = document.getElementById('generatedPlanSessions');

  const sessionsByDate = {};
  res.sessions.forEach(s => {
    if (!sessionsByDate[s.date]) sessionsByDate[s.date] = [];
    sessionsByDate[s.date].push(s);
  });
  const dates = Object.keys(sessionsByDate).sort();

  sessionsEl.innerHTML = dates.map(date => `
    <div class="study-day-group">
      <div class="study-day-label">${formatDate(date)}</div>
      ${sessionsByDate[date].map(s => `
        <div class="study-session-item">
          <span class="session-subject-tag">${s.subject}</span>
          <span class="session-topic-name">${s.topic}</span>
          <span class="session-dur">${s.duration}</span>
        </div>`).join('')}
    </div>`).join('');

  wrap.style.display = 'block';
  document.getElementById('savePlanBtn').style.display = 'inline-flex';
  showToast(`Plan generated! ${res.sessions.length} sessions over ${res.total_days} days.`);
});

document.getElementById('savePlanBtn').addEventListener('click', async () => {
  if (!generatedSessions || !generatedPlanMeta) return;
  const button = document.getElementById('savePlanBtn');
  button.disabled = true;
  try {
    const res = await Auth.apiFetch('/academics/study-plans/', {
      method: 'POST',
      body: JSON.stringify({ ...generatedPlanMeta, sessions: generatedSessions })
    });
    if (res) {
      showToast('Study plan saved!');
      document.getElementById('generatedPlanWrap').style.display = 'none';
      button.style.display = 'none';
      generatedSessions = null;
      generatedPlanMeta = null;
      await loadAll();
    } else showToast('Save failed.', 'error');
  } finally {
    button.disabled = false;
  }
});

async function deleteStudyPlan(id) {
  if (!confirm('Delete this study plan?')) return;
  const res = await fetch(`http://127.0.0.1:8000/api/academics/study-plans/${id}/`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${Auth.getToken()}` }
  });
  if (res.ok) { showToast('Plan deleted.'); await loadAll(); }
  else showToast('Delete failed.', 'error');
}

async function toggleSession(planId, sessionId, completed, checkbox) {
  checkbox.disabled = true;
  const res = await Auth.apiFetch(`/academics/study-plans/${planId}/`, {
    method: 'PATCH',
    body: JSON.stringify({ session_id: sessionId, is_completed: completed })
  });
  if (res) {
    await loadAll();
    showToast(completed ? 'Session completed.' : 'Session marked pending.');
  } else {
    checkbox.checked = !completed; // revert visual state
    checkbox.disabled = false;
    showToast('Failed to update session.', 'error');
  }
}

/* ===== RESCHEDULE ===== */
let reschedulePreviewData = null;

function openReschedule(planId, dailyHours) {
  document.getElementById('reschedulePlanId').value = planId;
  document.getElementById('rescheduleStartDate').value = '';
  document.getElementById('rescheduleEndDate').value = '';
  document.getElementById('rescheduleDailyHours').value = dailyHours || '2';
  openModal('rescheduleModal');
}

document.getElementById('rescheduleForm').addEventListener('submit', async e => {
  e.preventDefault();
  const planId = document.getElementById('reschedulePlanId').value;
  const start_date = document.getElementById('rescheduleStartDate').value;
  const end_date = document.getElementById('rescheduleEndDate').value;
  const daily_hours = parseInt(document.getElementById('rescheduleDailyHours').value);

  if (!start_date || !end_date) { showToast('Please fill in both dates.', 'error'); return; }
  if (end_date < start_date) { showToast('End date must be on or after start date.', 'error'); return; }

  const res = await Auth.apiFetch(`/academics/study-plans/${planId}/reschedule/`, {
    method: 'POST',
    body: JSON.stringify({ start_date, end_date, daily_hours })
  });

  if (!res) { showToast('Preview failed. Check your inputs.', 'error'); return; }

  reschedulePreviewData = { planId, start_date, end_date, daily_hours, sessions: res.new_sessions };

  const meta = document.getElementById('reschedulePreviewMeta');
  meta.innerHTML = [
    `<span style="color:var(--green)">✓ ${res.preserved_completed} completed session(s) preserved</span>`,
    `<span style="color:var(--primary-bright)"> · ${res.total_new} new session(s) scheduled</span>`,
    res.removed_pending ? `<span style="color:#fbbf24"> · ${res.removed_pending} pending session(s) replaced</span>` : '',
    res.unscheduled_topics ? `<span style="color:var(--muted)"> · ${res.unscheduled_topics} topic(s) couldn't fit in the date range</span>` : ''
  ].filter(Boolean).join('');

  const sessionsEl = document.getElementById('reschedulePreviewSessions');
  if (!res.new_sessions || !res.new_sessions.length) {
    sessionsEl.innerHTML = `<div class="dash-empty">${res.message}</div>`;
  } else {
    const byDate = {};
    res.new_sessions.forEach(s => { if (!byDate[s.date]) byDate[s.date] = []; byDate[s.date].push(s); });
    sessionsEl.innerHTML = Object.keys(byDate).sort().map(date => `
      <div class="study-day-group">
        <div class="study-day-label">${formatDate(date)}</div>
        ${byDate[date].map(s => `
          <div class="study-session-item">
            <span class="session-subject-tag">${s.subject}</span>
            <span class="session-topic-name">${s.topic}</span>
            <span class="session-dur">${s.duration}</span>
          </div>`).join('')}
      </div>`).join('');
  }

  closeModal('rescheduleModal');
  openModal('reschedulePreviewModal');
});

document.getElementById('confirmRescheduleBtn').addEventListener('click', async () => {
  if (!reschedulePreviewData) return;
  const { planId, start_date, end_date, daily_hours } = reschedulePreviewData;

  const res = await Auth.apiFetch(`/academics/study-plans/${planId}/reschedule/`, {
    method: 'PUT',
    body: JSON.stringify({ start_date, end_date, daily_hours })
  });

  if (res) {
    showToast('Plan rescheduled and saved!');
    closeModal('reschedulePreviewModal');
    reschedulePreviewData = null;
    await loadAll();
  } else {
    showToast('Failed to save reschedule.', 'error');
  }
});

/* ===== STUDY INSIGHTS ===== */
async function renderInsights() {
  const el = document.getElementById('studyInsightsWrap');
  const data = await Auth.apiFetch('/academics/insights/');
  if (!data) { el.innerHTML = `<div class="dash-empty">Could not load insights.</div>`; return; }

  const todayPct = data.today_total ? Math.round((data.today_done / data.today_total) * 100) : null;

  // Summary cards
  const summaryCards = [
    { label: 'Subjects', value: data.total_subjects, color: '#818cf8' },
    { label: 'Total Topics', value: data.total_topics, color: '#a78bfa' },
    { label: 'Completed Topics', value: data.completed_topics, color: '#34d399' },
    { label: 'Topic Progress', value: `${data.topic_completion_pct}%`, color: '#22d3ee' },
    { label: 'Total Sessions', value: data.total_sessions, color: '#818cf8' },
    { label: 'Done Sessions', value: data.completed_sessions, color: '#34d399' },
    { label: 'Pending Sessions', value: data.pending_sessions, color: '#fbbf24' },
  ];

  el.innerHTML = `
    <!-- Summary cards -->
    <div class="insights-summary-grid">
      ${summaryCards.map(c => `
        <div class="insight-summary-card">
          <div class="insight-summary-val" style="color:${c.color}">${c.value}</div>
          <div class="insight-summary-lbl">${c.label}</div>
        </div>`).join('')}
    </div>

    <!-- Session + Today progress -->
    <div class="insights-grid" style="margin-top:16px">
      <div class="insight-block">
        <div class="insight-label">Session Completion</div>
        <div class="insight-big">${data.session_completion_pct ?? data.completion_pct}%</div>
        <div class="progress-bar-wrap" style="margin-top:6px">
          <div class="progress-bar" style="width:${data.session_completion_pct ?? data.completion_pct}%"></div>
        </div>
        <div class="insight-sub">${data.completed_sessions} done · ${data.pending_sessions} pending</div>
      </div>

      <div class="insight-block">
        <div class="insight-label">Today's Sessions</div>
        ${data.today_total
          ? `<div class="insight-big">${data.today_done}/${data.today_total}</div>
             <div class="progress-bar-wrap" style="margin-top:6px">
               <div class="progress-bar" style="width:${todayPct}%"></div>
             </div>
             <div class="insight-sub">${todayPct}% complete today</div>`
          : `<div class="insight-sub" style="margin-top:8px">No sessions scheduled today</div>`}
      </div>

      <div class="insight-block">
        <div class="insight-label">Urgent Assignments</div>
        ${data.urgent_assignments.length
          ? data.urgent_assignments.map(a =>
              `<div class="insight-row">
                <span class="insight-row-name">${a.title}</span>
                ${priorityBadge(a.priority)}
              </div>`).join('')
          : `<div class="insight-sub" style="margin-top:8px">No urgent assignments 🎉</div>`}
      </div>

      <div class="insight-block">
        <div class="insight-label">Topic Completion</div>
        <div class="insight-big">${data.topic_completion_pct}%</div>
        <div class="progress-bar-wrap" style="margin-top:6px">
          <div class="progress-bar" style="width:${data.topic_completion_pct}%"></div>
        </div>
        <div class="insight-sub">${data.completed_topics} of ${data.total_topics} topics done</div>
      </div>
    </div>

    <!-- Subject-wise progress -->
    ${data.subject_progress && data.subject_progress.length
      ? `<div style="margin-top:20px">
          <div class="insight-label" style="margin-bottom:10px">Subject-wise Progress</div>
          <div class="insights-topics-grid">
            ${data.subject_progress.map(s => `
              <div class="insight-topic-row">
                <div style="display:flex;justify-content:space-between;margin-bottom:4px">
                  <span style="color:var(--text-bright);font-size:0.8rem;font-weight:600">${s.subject}</span>
                  <span style="color:var(--muted);font-size:0.72rem">${s.completed_topics}/${s.total_topics}</span>
                </div>
                <div class="progress-bar-wrap">
                  <div class="progress-bar" style="width:${s.completion_pct}%"></div>
                </div>
                <div style="color:var(--muted);font-size:0.68rem;margin-top:3px">${s.completion_pct}% complete</div>
              </div>`).join('')}
          </div>
        </div>`
      : ''}

    <!-- Upcoming exams -->
    ${data.upcoming_exams && data.upcoming_exams.length
      ? `<div style="margin-top:20px">
          <div class="insight-label" style="margin-bottom:10px">Upcoming Exams</div>
          <div class="insights-exams-list">
            ${data.upcoming_exams.map(e => `
              <div class="insight-exam-row">
                <div class="insight-exam-info">
                  <span class="insight-row-name">${e.title}</span>
                  ${e.subject ? `<span style="color:var(--muted);font-size:0.72rem"> · ${e.subject}</span>` : ''}
                  <div style="color:var(--muted);font-size:0.7rem;margin-top:2px">📅 ${formatDate(e.exam_date)}</div>
                </div>
                <span class="exam-days-badge ${e.days_until === 0 ? 'days-soon' : e.days_until <= 3 ? 'days-soon' : e.days_until <= 7 ? 'days-upcoming' : 'days-far'}">
                  ${e.days_until === 0 ? 'Today' : `In ${e.days_until}d`}
                </span>
              </div>`).join('')}
          </div>
        </div>`
      : `<div style="margin-top:16px"><div class="insight-sub" style="text-align:center">No upcoming exams 🎉</div></div>`}
  `;
}

/* ===== LOAD ===== */
loadAll();
