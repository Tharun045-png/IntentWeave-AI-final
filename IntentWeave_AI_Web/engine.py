"""Modules 2 and 3: contextual intent classification and verified local actions."""
from __future__ import annotations

import ast
import operator
import re
from dataclasses import dataclass, field

from database import Store


PROJECT_KNOWLEDGE = {
    'module1': ('**Module 1 — Multimodal Command Recognition** accepts text, recorded voice, and image uploads. '
                'It identifies each input type, transcribes speech when available, extracts useful image information, '
                'and standardizes the result for the next module.'),
    'module2': ('**Module 2 — Contextual Intent Reasoning** analyzes commands, key phrases, and relevant conversation '
                'history to determine whether the user needs information, an explanation, or an action.'),
    'module3': ('**Module 3 — Verified Action Execution** checks required information, asks the user to confirm '
                'changes, and reports the result after performing an approved supported operation.'),
    'overview': ('**IntentWeave AI** is a context-aware multimodal assistant from the capstone presentation. '
                 'Its pipeline is: text / voice / image → command recognition → contextual intent reasoning '
                 '→ verified action execution → response, with recent conversation history used for context.'),
}


@dataclass
class Intent:
    name: str
    explanation: str
    data: dict = field(default_factory=dict)
    requires_approval: bool = False


def classify(text: str, history: list[dict] | None = None) -> Intent:
    cleaned = ' '.join(text.strip().split())
    low = cleaned.lower().strip(' ?.!')
    patterns = [
        (r'^(?:please )?(?:add|create|make) (?:a |new )?(?:task|to-do|todo)(?: called| named| to|:| -)?\s*(.+)$', 'task_add'),
        (r'^(?:remind me to|i need to)\s+(.+)$', 'task_add'),
        (r'^(?:save|write|create|add) (?:a )?note(?: that|:| -)?\s*(.+)$', 'note_add'),
        (r'^(?:remember that)\s+(.+)$', 'note_add'),
    ]
    for pattern, name in patterns:
        m = re.match(pattern, cleaned, flags=re.I)
        if m and m.group(1).strip():
            return Intent(name, 'Recognized a supported local write action.',
                          {'text': m.group(1).strip()[:1200]}, True)

    if re.search(r'\b(?:show|list|display|view)\b.*\b(?:my )?(?:tasks|to-?dos)\b', low):
        return Intent('task_list', 'Task-list request detected.')
    if re.search(r'\b(?:show|list|display|view)\b.*\b(?:my )?notes\b', low):
        return Intent('note_list', 'Notes-list request detected.')
    if re.match(r'^(?:mark|complete|finish|check off)\b', low) and ('task' in low or 'done' in low or low in ('complete it', 'mark it done', 'finish it')):
        m = re.search(r'(?:task\s*#?\s*|#)(\d+)', low)
        return Intent('task_complete', 'Task completion needs approval.', {'task_id': int(m.group(1)) if m else None}, True)
    if 'summari' in low and any(x in low for x in ('chat', 'conversation', 'messages', 'said')):
        return Intent('summary', 'Conversation summary requested.')
    if any(x in low for x in ('what can you do', 'how to use', 'help me', 'your features')) or low == 'help':
        return Intent('help', 'Help request detected.')

    math_match = re.match(r'^(?:calculate|compute|solve|evaluate)\s+(.+)$', cleaned, flags=re.I)
    if not math_match:
        math_match = re.match(r'^what (?:is|does)\s+([0-9\s\+\-\*\/\%\^\.\(\)]+?)(?:\s*\?)?$', cleaned, flags=re.I)
    if math_match:
        return Intent('calculate', 'Mathematical expression detected.', {'expression': math_match.group(1)})

    # This also recognizes natural follow-up questions such as "what about module 2?".
    module = re.search(r'\bmodule\s*(?:number\s*)?([123])\b', low)
    if module:
        return Intent('project_info', 'Matched a module in the presentation.', {'section': 'module' + module.group(1)})
    ordinal = re.search(r'\b(first|second|third) module\b', low)
    if ordinal:
        number = {'first': '1', 'second': '2', 'third': '3'}[ordinal.group(1)]
        return Intent('project_info', 'Matched a module in the presentation.', {'section': 'module' + number})
    if any(x in low for x in ('about intentweave', 'about the project', 'project overview', 'architecture', 'three modules')):
        return Intent('project_info', 'Matched project overview.', {'section':'overview'})

    # A short reference to a previous module question.
    if low in ('what about it', 'explain more', 'tell me more', 'how does it work'):
        for entry in reversed(history or []):
            if entry.get('role') == 'user':
                found = re.search(r'\bmodule\s*([123])\b', entry.get('content', '').lower())
                if found:
                    return Intent('project_info', 'Resolved follow-up using conversation context.', {'section':'module'+found.group(1)})
    if history and re.search(r'\b(?:it|its|they|them|that|this|those|these|their|there)\b', low):
        return Intent('follow_up', 'Follow-up reference detected; recent conversation may provide context.',
                      {'reference':re.search(r'\b(?:it|its|they|them|that|this|those|these|their|there)\b', low).group(0)})
    if re.search(r'\bartificial intelligence\b', low) or re.search(r'\bai\b', low):
        return Intent('ai_overview', 'Matched an introductory artificial-intelligence topic.')
    return Intent('general', 'General question; use configured model or explain demo limitations.')


_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.UAdd: lambda x: x,
    ast.USub: operator.neg,
}


def safe_calculate(expression: str) -> float:
    """Arithmetic-only AST interpreter; no eval, identifiers, attributes or calls."""
    expression = expression.replace('×', '*').replace('÷', '/').replace('^', '**')
    if not expression.strip() or len(expression) > 120:
        raise ValueError('Enter a short arithmetic expression.')
    root = ast.parse(expression, mode='eval')

    def visit(node):
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            if abs(node.value) > 1e12:
                raise ValueError('Number is too large.')
            return node.value
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPERATORS:
            result = _OPERATORS[type(node.op)](visit(node.operand))
        elif isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Pow) and (abs(left) > 1e6 or abs(right) > 8):
                raise ValueError('Exponent is too large.')
            result = _OPERATORS[type(node.op)](left, right)
        else:
            raise ValueError('Only numbers, parentheses, +, -, *, /, //, %, and ^ are allowed.')
        if isinstance(result, complex) or abs(result) > 1e12:
            raise ValueError('Result is too large.')
        return result

    try:
        answer = visit(root)
    except (SyntaxError, ZeroDivisionError, OverflowError, TypeError) as exc:
        raise ValueError(f'Invalid calculation: {exc}') from exc
    return float(answer) if isinstance(answer, float) else answer


def execute_approved(store: Store, cid: str, intent: Intent, request_id: str | None = None) -> str:
    """Execute only explicitly whitelisted, validated changes after UI confirmation."""
    if not intent.requires_approval:
        raise ValueError('This is not a confirmable action.')
    if intent.name == 'task_add':
        title = intent.data.get('text', '').strip()
        if not 1 <= len(title) <= 1200:
            raise ValueError('Task must be between 1 and 1,200 characters.')
        task_id = store.create_task_and_log(cid, title, request_id)
        return f'✅ Task **#{task_id}** created: {title}\n\nTasks are stored locally; this demo does not send reminders.'
    if intent.name == 'note_add':
        body = intent.data.get('text', '').strip()
        if not 1 <= len(body) <= 1200:
            raise ValueError('Note must be between 1 and 1,200 characters.')
        note_id = store.create_note_and_log(cid, body, request_id)
        return f'✅ Note **#{note_id}** saved to your local workspace.'
    if intent.name == 'task_complete':
        task_id = intent.data.get('task_id')
        if not isinstance(task_id, int) or not store.complete_task_and_log(cid, task_id, request_id):
            raise ValueError('The selected open task no longer exists.')
        return f'✅ Task **#{task_id}** marked complete.'
    raise ValueError('Unsupported action. No changes were made.')


def local_response(intent: Intent, store: Store, cid: str, history: list[dict]):
    if intent.name == 'ai_overview':
        return ('**Artificial intelligence (local overview):**\n\n'
                'Artificial intelligence is a field focused on systems that perform tasks commonly associated '
                'with human reasoning or perception, such as understanding language, recognizing patterns, '
                'and making predictions. IntentWeave demonstrates a small rule-based version of these ideas.')
    low = ''
    if history:
        low = ' '.join(str(m.get('content', '')).lower() for m in history[-6:])
    if intent.name == 'follow_up' and 'artificial intelligence' in low:
        return ('**Applications of artificial intelligence (local overview):**\n\n'
                'AI is commonly used in healthcare support, education, customer service, transportation, '
                'finance, manufacturing, and multimedia analysis. These are general examples; this rule-based '
                'demo does not verify real-world claims or perform any external service.')
    if intent.name == 'general' and re.search(r'\b(?:what is|define|explain)\b.*\bartificial intelligence\b', history[-1]['content'].lower() if history else ''):
        pass
    if intent.name == 'project_info':
        return PROJECT_KNOWLEDGE[intent.data['section']]
    if intent.name == 'help':
        return ('**Try these commands:**\n\n'
                '- `Add a task to prepare my capstone presentation`\n'
                '- `Show my tasks` → `Mark it done`\n'
                '- `Save a note: Context is shared across turns`\n'
                '- `Show my notes`\n'
                '- `Calculate (45 + 15) / 3`\n'
                '- `What does Module 2 do?`\n'
                '- Upload an image with “Analyze this image”\n\n'
                'Add an optional AI API key for open-ended answers, visual understanding, and voice transcription.')
    if intent.name == 'task_list':
        tasks = store.tasks(cid)
        if not tasks:
            return 'No tasks saved in this conversation. Try `Add a task to review the report`.'
        return '**Your tasks**\n\n' + '\n'.join(f"{'✅' if t['done'] else '⬜'} #{t['id']} — {t['title']}" for t in tasks)
    if intent.name == 'note_list':
        notes = store.notes(cid)
        if not notes:
            return 'No notes saved in this conversation. Try `Save a note: Our demo is tomorrow`.'
        return '**Your notes**\n\n' + '\n'.join(f"- **#{n['id']}** {n['body']}" for n in notes)
    if intent.name == 'summary':
        asked = [m['content'] for m in history if m.get('role') == 'user'][-6:]
        return ('**Recent user requests**\n\n' + '\n'.join(f'- {x[:250]}' for x in asked)) if asked else 'There are no previous messages to summarize.'
    if intent.name == 'calculate':
        try:
            value = safe_calculate(intent.data['expression'])
            return f"**Result:** `{intent.data['expression']}` = **{value:,}**"
        except ValueError as exc:
            return f"Couldn't calculate that expression: {exc}"
    return None


def prepare_proposal(intent: Intent, store: Store, cid: str):
    """Validation before approval; no database changes here."""
    if intent.name in ('task_add','note_add'):
        content = intent.data.get('text', '').strip()
        if not content:
            return None, 'Please provide some text for the task or note.'
        return intent, None
    if intent.name == 'task_complete':
        task = store.task_by_id(cid, intent.data['task_id']) if intent.data.get('task_id') else store.latest_open_task(cid)
        if task is None or task['done']:
            return None, 'No matching unfinished task found. Use `Show my tasks` to check available IDs.'
        intent.data['task_id'] = task['id']
        intent.data['text'] = task['title']
        return intent, None
    return None, 'Unsupported operation.'
