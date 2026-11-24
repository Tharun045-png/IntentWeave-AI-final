"""SQLite persistence for the single-user IntentWeave AI academic demonstration."""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')


class Store:
    def __init__(self, path: str | Path | None = None):
        configured = path or os.getenv('INTENTWEAVE_DB', 'data/intentweave.sqlite3')
        self.path = Path(configured)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.setup()

    def connect(self):
        connection = sqlite3.connect(str(self.path), timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        return connection

    def setup(self):
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        owner_id TEXT
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    modality TEXT NOT NULL DEFAULT 'text',
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    done INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                    body TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS action_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                    action TEXT NOT NULL,
                    details TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    request_id TEXT
                );
            ''')
            columns = {row['name'] for row in db.execute('PRAGMA table_info(action_logs)')}
            if 'request_id' not in columns:
                db.execute('ALTER TABLE action_logs ADD COLUMN request_id TEXT')
            conversation_columns = {row['name'] for row in db.execute('PRAGMA table_info(conversations)')}
            if 'owner_id' not in conversation_columns:
                db.execute('ALTER TABLE conversations ADD COLUMN owner_id TEXT')

    def start_conversation(self, title='New conversation', owner_id=None):
        identifier = str(uuid.uuid4())
        with self.connect() as db:
            db.execute('INSERT INTO conversations (id,title,created_at,owner_id) VALUES (?, ?, ?, ?)',
                       (identifier, title, utc_now(), owner_id))
        return identifier

    def conversation_exists(self, cid, owner_id=None):
        with self.connect() as db:
            if owner_id is None:
                return db.execute('SELECT 1 FROM conversations WHERE id=?', (cid,)).fetchone() is not None
            return db.execute('SELECT 1 FROM conversations WHERE id=? AND owner_id=?',
                              (cid, owner_id)).fetchone() is not None

    def conversations(self, owner_id=None):
        with self.connect() as db:
            if owner_id is None:
                rows = db.execute('SELECT * FROM conversations ORDER BY rowid DESC')
            else:
                rows = db.execute(
                    'SELECT * FROM conversations WHERE owner_id=? ORDER BY rowid DESC',
                    (owner_id,))
            return [dict(row) for row in rows]

    def messages(self, cid, limit=100):
        with self.connect() as db:
            rows = db.execute('SELECT * FROM (SELECT * FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT ?) ORDER BY id', (cid, limit))
            return [dict(row) for row in rows]

    def add_message(self, cid, role, content, modality='text', metadata=None):
        with self.connect() as db:
            cur = db.execute('INSERT INTO messages (conversation_id,role,content,modality,metadata,created_at) VALUES (?,?,?,?,?,?)',
                             (cid, role, content[:16000], modality, json.dumps(metadata or {}), utc_now()))
            if role == 'user':
                count = db.execute('SELECT COUNT(*) FROM messages WHERE conversation_id=? AND role="user"', (cid,)).fetchone()[0]
                if count == 1:
                    db.execute('UPDATE conversations SET title=? WHERE id=?', (content[:40].strip() or 'Image / voice conversation', cid))
            return cur.lastrowid

    def tasks(self, cid):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM tasks WHERE conversation_id=? ORDER BY id DESC', (cid,))]

    def task_by_id(self, cid, task_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM tasks WHERE conversation_id=? AND id=?', (cid, task_id)).fetchone()
            return dict(row) if row else None

    def latest_open_task(self, cid):
        with self.connect() as db:
            row = db.execute('SELECT * FROM tasks WHERE conversation_id=? AND done=0 ORDER BY id DESC LIMIT 1', (cid,)).fetchone()
            return dict(row) if row else None

    def create_task(self, cid, title):
        with self.connect() as db:
            cur = db.execute('INSERT INTO tasks (conversation_id,title,created_at) VALUES (?,?,?)', (cid, title, utc_now()))
            return cur.lastrowid

    def create_task_and_log(self, cid, title, request_id=None):
        created_at = utc_now()
        with self.connect() as db:
            if request_id:
                existing = db.execute(
                    'SELECT action,details,status FROM action_logs WHERE conversation_id=? AND request_id=? AND status="completed"',
                    (cid, request_id)).fetchone()
                if existing:
                    return int(existing['details'].split(':', 1)[0].replace('#', '').strip())
            cur = db.execute('INSERT INTO tasks (conversation_id,title,created_at) VALUES (?,?,?)',
                             (cid, title, created_at))
            task_id = cur.lastrowid
            db.execute('''INSERT INTO action_logs
                (conversation_id,action,details,status,created_at,request_id)
                VALUES (?,?,?,?,?,?)''',
                       (cid, 'Create task', f'#{task_id}: {title}'[:1000], 'completed', created_at, request_id))
            return task_id

    def complete_task(self, cid, task_id):
        with self.connect() as db:
            cur = db.execute('UPDATE tasks SET done=1 WHERE id=? AND conversation_id=? AND done=0', (task_id, cid))
            return cur.rowcount > 0

    def notes(self, cid):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM notes WHERE conversation_id=? ORDER BY id DESC', (cid,))]

    def create_note(self, cid, body):
        with self.connect() as db:
            cur = db.execute('INSERT INTO notes (conversation_id,body,created_at) VALUES (?,?,?)', (cid, body, utc_now()))
            return cur.lastrowid

    def create_note_and_log(self, cid, body, request_id=None):
        created_at = utc_now()
        with self.connect() as db:
            if request_id:
                existing = db.execute(
                    'SELECT details FROM action_logs WHERE conversation_id=? AND request_id=? AND status="completed"',
                    (cid, request_id)).fetchone()
                if existing:
                    return int(existing['details'].split(':', 1)[0].replace('#', '').strip())
            cur = db.execute('INSERT INTO notes (conversation_id,body,created_at) VALUES (?,?,?)',
                             (cid, body, created_at))
            note_id = cur.lastrowid
            db.execute('''INSERT INTO action_logs
                (conversation_id,action,details,status,created_at,request_id)
                VALUES (?,?,?,?,?,?)''',
                       (cid, 'Save note', f'#{note_id}: {body}'[:1000], 'completed', created_at, request_id))
            return note_id

    def complete_task_and_log(self, cid, task_id, request_id=None):
        created_at = utc_now()
        with self.connect() as db:
            if request_id:
                existing = db.execute(
                    'SELECT 1 FROM action_logs WHERE conversation_id=? AND request_id=? AND status="completed"',
                    (cid, request_id)).fetchone()
                if existing:
                    return True
            cur = db.execute('UPDATE tasks SET done=1 WHERE id=? AND conversation_id=? AND done=0',
                             (task_id, cid))
            if not cur.rowcount:
                return False
            db.execute('''INSERT INTO action_logs
                (conversation_id,action,details,status,created_at,request_id)
                VALUES (?,?,?,?,?,?)''',
                       (cid, 'Complete task', f'#{task_id}', 'completed', created_at, request_id))
            return True

    def log_action(self, cid, action, details, status, request_id=None):
        with self.connect() as db:
            db.execute('INSERT INTO action_logs (conversation_id,action,details,status,created_at,request_id) VALUES (?,?,?,?,?,?)',
                       (cid, action, details[:1000], status, utc_now(), request_id))

    def actions(self, cid):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM action_logs WHERE conversation_id=? ORDER BY id DESC', (cid,))]

    def stats(self, cid):
        with self.connect() as db:
            return {
                'messages': db.execute('SELECT COUNT(*) FROM messages WHERE conversation_id=? AND role="user"', (cid,)).fetchone()[0],
                'open_tasks': db.execute('SELECT COUNT(*) FROM tasks WHERE conversation_id=? AND done=0', (cid,)).fetchone()[0],
                'notes': db.execute('SELECT COUNT(*) FROM notes WHERE conversation_id=?', (cid,)).fetchone()[0],
                'actions': db.execute('SELECT COUNT(*) FROM action_logs WHERE conversation_id=? AND status="completed"', (cid,)).fetchone()[0],
            }

    def analytics(self, owner_id=None):
        with self.connect() as db:
            owner_filter = ''
            params = ()
            if owner_id:
                owner_filter = ' WHERE conversation_id IN (SELECT id FROM conversations WHERE owner_id=?)'
                params = (owner_id,)
            messages = [dict(row) for row in db.execute(
                'SELECT role, content, modality, metadata, created_at FROM messages'
                + owner_filter.replace('conversation_id', 'messages.conversation_id')
                + ' ORDER BY messages.id DESC', params)]
            actions = [dict(row) for row in db.execute(
                'SELECT action, details, status, created_at, request_id FROM action_logs'
                + owner_filter.replace('conversation_id', 'action_logs.conversation_id')
                + ' ORDER BY action_logs.id DESC', params)]
            latest_status_by_request = {}
            for action in reversed(actions):
                if action.get('request_id'):
                    latest_status_by_request[action['request_id']] = action['status']
            totals = {
                'commands': sum(message['role'] == 'user' for message in messages),
                'completed_actions': sum(action['status'] == 'completed' for action in actions),
                'pending_approvals': sum(status == 'pending' for status in latest_status_by_request.values())
                    + sum(action['status'] == 'pending' and not action.get('request_id') for action in actions),
            }

        modalities = {}
        intents = {}
        for message in messages:
            if message['role'] != 'user':
                continue
            for modality in message['modality'].split('+'):
                modalities[modality] = modalities.get(modality, 0) + 1
        for message in messages:
            if message['role'] != 'assistant':
                continue
            try:
                intent = json.loads(message['metadata']).get('intent')
            except (TypeError, ValueError):
                intent = None
            if intent:
                intents[intent] = intents.get(intent, 0) + 1
        return {
            **totals,
            'modalities': modalities,
            'intents': intents,
            'recent_messages': list(reversed(messages[:10])),
            'recent_actions': actions[:10],
        }

    def export_conversation(self, cid):
        return json.dumps({
            'conversation_id': cid,
            'messages': self.messages(cid),
            'tasks': self.tasks(cid),
            'notes': self.notes(cid),
            'action_logs': self.actions(cid),
        }, indent=2, ensure_ascii=False)

    def delete_conversation(self, cid):
        with self.connect() as db:
            db.execute('DELETE FROM conversations WHERE id=?', (cid,))
