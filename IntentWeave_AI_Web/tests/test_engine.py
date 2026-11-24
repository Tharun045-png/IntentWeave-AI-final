import sqlite3

from database import Store
from engine import classify, execute_approved, local_response, prepare_proposal, safe_calculate


def test_intent_recognition():
    assert classify('Add a task to prepare slides').name == 'task_add'
    assert classify('Save a note: final demo at 3').name == 'note_add'
    assert classify('What does Module 2 do?').data['section'] == 'module2'
    assert classify('Show my notes').name == 'note_list'
    assert classify('Calculate (2+3)*5').name == 'calculate'
    assert classify('Create a task called Prepare capstone presentation').data['text'] == 'Prepare capstone presentation'


def test_safe_arithmetic():
    assert safe_calculate('(2 + 3) * 5') == 25
    assert safe_calculate('2^3') == 8
    for expression in ['__import__("os")', '1/0', '100**100', 'max(2,3)']:
        try:
            safe_calculate(expression)
        except ValueError:
            pass
        else:
            raise AssertionError(f'Unsafe arithmetic expression accepted: {expression}')


def test_confirmation_required_and_data_is_separated(tmp_path):
    store = Store(tmp_path / 'demo.sqlite3')
    first = store.start_conversation()
    second = store.start_conversation()
    intent = classify('Add a task to prepare slides')
    proposed, error = prepare_proposal(intent, store, first)
    assert error is None
    assert store.tasks(first) == []  # proposing must never execute
    result = execute_approved(store, first, proposed)
    assert 'created' in result
    assert len(store.tasks(first)) == 1
    assert store.tasks(second) == []
    note = classify('Save a note: final demo is Friday')
    proposed_note, error = prepare_proposal(note, store, first)
    assert error is None
    assert store.notes(first) == []
    execute_approved(store, first, proposed_note)
    assert store.notes(first)[0]['body'] == 'final demo is Friday'
    completed = classify('Mark it done')
    proposed, error = prepare_proposal(completed, store, first)
    assert error is None
    assert store.tasks(first)[0]['done'] == 0  # no changes before confirmation
    execute_approved(store, first, proposed)
    assert store.tasks(first)[0]['done'] == 1
    assert store.stats(first)['actions'] == 3


def test_contextual_followup():
    previous = [{'role': 'user', 'content': 'What is Module 3?'}]
    assert classify('Tell me more', previous).data['section'] == 'module3'
    general_context = [{'role':'user', 'content':'Explain artificial intelligence in simple words.'}]
    assert classify('Explain its applications.', general_context).name == 'follow_up'


def test_database_analytics_tracks_input_and_current_approval_state(tmp_path):
    store = Store(tmp_path / 'analytics.sqlite3')
    cid = store.start_conversation()
    store.add_message(cid, 'user', 'Create a task called Prepare slides', 'text+voice')
    store.add_message(cid, 'assistant', 'Approval required', metadata={'intent':'task_add'})
    store.log_action(cid, 'Create task', 'Prepare slides', 'pending', 'request-1')
    assert store.analytics()['pending_approvals'] == 1
    store.log_action(cid, 'Create task', 'Prepare slides', 'confirmed', 'request-1')
    store.log_action(cid, 'Create task', 'Prepare slides', 'completed', 'request-1')
    results = store.analytics()
    assert results['commands'] == 1
    assert results['modalities'] == {'text': 1, 'voice': 1}
    assert results['intents'] == {'task_add': 1}
    assert results['pending_approvals'] == 0
    assert results['completed_actions'] == 1


def test_existing_action_log_schema_migrates_request_id(tmp_path):
    path = tmp_path / 'legacy.sqlite3'
    with sqlite3.connect(path) as db:
        db.execute('''CREATE TABLE action_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            action TEXT NOT NULL,
            details TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        )''')
    Store(path)
    db = sqlite3.connect(path)
    columns = {row[1] for row in db.execute('PRAGMA table_info(action_logs)')}
    db.close()
    assert 'request_id' in columns


def test_ordinal_modules_and_database_export(tmp_path):
    assert classify('Explain the second module').data['section'] == 'module2'
    store = Store(tmp_path / 'export.sqlite3')
    cid = store.start_conversation()
    store.add_message(cid, 'user', 'How does it work?')
    exported = store.export_conversation(cid)
    assert 'How does it work?' in exported
    assert 'conversation_id' in exported
