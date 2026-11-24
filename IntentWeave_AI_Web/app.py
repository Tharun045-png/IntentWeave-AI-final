"""IntentWeave AI — Context-Aware Multimodal Assistant (Streamlit UI)."""
from __future__ import annotations

import json
import hashlib
import os
import re
import sqlite3
import uuid
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

from database import Store
from engine import Intent, classify, execute_approved, local_response, prepare_proposal
from media import analyze_image, api_key, ask_model, image_report, transcribe_audio, validate_image

load_dotenv(Path(__file__).resolve().parent / '.env')
st.set_page_config(page_title='IntentWeave AI • Multimodal Assistant', page_icon='🧠',
                   layout='wide', initial_sidebar_state='expanded')

st.markdown('''
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
  html,body,[class*="css"],.stApp { font-family:'DM Sans',sans-serif; }
  .stApp { background: radial-gradient(circle at 75% 3%,rgba(80,65,170,.20),transparent 33%),
                      radial-gradient(circle at 15% 40%,rgba(11,112,138,.08),transparent 30%),#0B1020; }
  h1,h2,h3 {font-family:'Space Grotesk',sans-serif;letter-spacing:-.03em;}
  [data-testid="stSidebar"] { background: #10172A; border-right: 1px solid #25314C; }
  [data-testid="stSidebar"] hr {border-color:#25314C;}
  [data-testid="stMainBlockContainer"] { padding-top:1.5rem; max-width:1200px; }
  .hero { background:linear-gradient(110deg,rgba(68,55,135,.40),rgba(20,51,83,.31));
          border:1px solid #38426C;border-radius:22px;padding:29px 32px;margin-bottom:20px; }
  .eyebrow {font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:#BFB2FF;font-weight:700;}
  .hero h1 {font-size:2.25rem;margin:8px 0 8px;color:#FAFBFF;}
  .hero p {font-size:1rem;color:#BAC7E0;max-width:780px;margin:0;line-height:1.65;}
  .pill {display:inline-block;border:1px solid #4F557E;border-radius:999px;color:#D0C5FF;
        font-size:12px;font-weight:600;padding:5px 11px;margin-right:7px;margin-top:14px;background:#181C40;}
  .metric {background:#141D33;border:1px solid #273653;border-radius:16px;padding:19px 20px;}
  .metric .value {font-size:1.95rem;line-height:1.1;font-weight:700;color:#F8FAFF;}
  .metric .name {color:#A6B4CF;font-size:13px;margin-top:7px;}
  .step {background:#141D33;border:1px solid #34415D;padding:20px;border-radius:16px;min-height:180px;}
  .step .num {color:#AA9BFF;font-size:12px;font-weight:700;letter-spacing:.08em;}
  .step .heading {font-weight:700;font-size:18px;margin:11px 0 7px;color:#E9EDFF;}
  .step .desc {font-size:13px;color:#B2BFD6;line-height:1.65;}
  .section-label {font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:#9EADD1;font-weight:700;margin:15px 0 10px;}
  .brand {font-family:'Space Grotesk',sans-serif;font-size:24px;font-weight:700;color:#F7F8FF;margin:4px 0 2px;}
  .brandmark {display:inline-flex;align-items:center;justify-content:center;vertical-align:middle;width:39px;height:39px;
       border-radius:12px;background:linear-gradient(135deg,#957CFF,#40C9CE);color:white;margin-right:10px;}
  .subtle {color:#9CAAC7;font-size:13px;line-height:1.5;}
  .workspace-item {background:#141D33;border:1px solid #2A3959;border-radius:12px;padding:13px 17px;margin:7px 0;}
  .mini-divider {height:1px;background:#28334C;margin:16px 0;}
  .stButton>button[kind="primary"], .stFormSubmitButton>button[kind="primary"] {border-radius:12px;
       background:linear-gradient(90deg,#7664E6,#5A86E8);border:0;font-weight:700;min-height:42px;}
  .stButton>button {border-radius:10px;}
  [data-testid="stChatMessage"] {background:#121B30;border:1px solid #273653;border-radius:16px;margin:9px 0;padding:10px;}
  [data-testid="stFileUploader"], [data-testid="stAudioInput"] {border-radius:12px;}
  @media (max-width:700px) {.hero {padding:20px;} .hero h1{font-size:1.7rem;}}
</style>
''', unsafe_allow_html=True)

@st.cache_resource
def load_store():
    return Store(os.getenv('INTENTWEAVE_DB') or (Path(__file__).resolve().parent / 'data' / 'intentweave.sqlite3'))

store = load_store()
if 'owner_id' not in st.session_state:
    st.session_state.owner_id = str(uuid.uuid4())
owner_id = st.session_state.owner_id
if 'conversation_id' not in st.session_state or not store.conversation_exists(st.session_state.conversation_id, owner_id):
    st.session_state.conversation_id = store.start_conversation(owner_id=owner_id)
if 'pending' not in st.session_state:
    st.session_state.pending = None
if 'section' not in st.session_state:
    st.session_state.section = 'Home'
if 'pending_navigation' in st.session_state:
    st.session_state.section = st.session_state.pending_navigation
    del st.session_state.pending_navigation


def navigate(page):
    st.session_state.pending_navigation = page


def on_nav_change():
    navigate(st.session_state.nav_radio)

cid = st.session_state.conversation_id

ACTION_LABELS = {
    'task_add':'Create task',
    'note_add':'Save note',
    'task_complete':'Complete task',
}


def queue_command(command):
    st.session_state.draft = command


def stage_action(intent):
    if st.session_state.pending and st.session_state.pending['cid'] == cid:
        return False
    label = ACTION_LABELS.get(intent.name, intent.name)
    request_id = str(uuid.uuid4())
    store.log_action(cid, label, intent.data.get('text', ''), 'pending', request_id)
    st.session_state.pending = {'cid':cid, 'intent':intent, 'request_id':request_id}
    return True


def speak_response(text):
    safe_text = json.dumps(text).replace('<', '\\u003c')
    components.html(
        f"""<button id="speak" style="border:1px solid #536080;border-radius:8px;padding:6px 10px;
        background:#151d33;color:#dce5ff;cursor:pointer;font:13px sans-serif">Speak response</button>
        <script>
        const phrase = {safe_text};
        document.getElementById("speak").addEventListener("click", () => {{
          window.speechSynthesis.cancel();
          window.speechSynthesis.speak(new SpeechSynthesisUtterance(phrase));
        }});
        </script>""",
        height=42,
    )


def show_metrics():
    stats = store.stats(cid)
    cols = st.columns(4, gap='medium')
    labels = [('messages','Messages'),('open_tasks','Open tasks'),('notes','Saved notes'),('actions','Approved actions')]
    for col, (key, label) in zip(cols, labels):
        with col:
            st.markdown(f'<div class="metric"><div class="value">{stats[key]}</div>'
                        f'<div class="name">{label}</div></div>', unsafe_allow_html=True)


def confirmation_ui():
    pending = st.session_state.pending
    if not pending or pending['cid'] != cid:
        return
    intent = pending['intent']
    label = ACTION_LABELS.get(intent.name, 'Action')
    st.markdown('#### Review before execution')
    st.info(f"**Proposed operation:** {label}\n\n**Details:** {intent.data.get('text','')}\n\n"
            'Nothing has been changed yet. Only approved actions are executed.')
    left, right, spacer = st.columns([1.4,1.4,5])
    with left:
        if st.button('✓ Confirm', type='primary', key='confirm_action', use_container_width=True):
            request_id = pending['request_id']
            store.log_action(cid, label, intent.data.get('text',''), 'confirmed', request_id)
            try:
                message = execute_approved(store, cid, intent, request_id)
            except (ValueError, sqlite3.Error) as exc:
                message = f'⚠️ Action was not completed: {exc}'
                store.log_action(cid, intent.name, intent.data.get('text',''), 'failed', request_id)
            status = 'completed' if message.startswith('✅') else 'failed'
            store.add_message(cid, 'assistant', message, metadata={'intent':'verified_action','status':status})
            st.session_state.pending = None
            st.rerun()
    with right:
        if st.button('✕ Cancel', key='cancel_action', use_container_width=True):
            store.log_action(cid, label, intent.data.get('text',''), 'cancelled', pending['request_id'])
            store.add_message(cid, 'assistant', 'Action canceled. No changes were made.',
                              metadata={'intent':'verified_action', 'status':'cancelled'})
            st.session_state.pending = None
            st.rerun()


def handle_message(text: str, image_bytes: bytes | None = None, image_name: str = '',
                   mime: str = 'image/jpeg', used_voice: bool = False, used_text: bool = True):
    text = text.strip()
    if not text and image_bytes:
        text = 'Analyze this image.'
    if not text:
        st.warning('Enter a message, record speech, or attach an image.')
        return
    history = store.messages(cid, limit=16)
    modalities = (['text'] if used_text else []) + (['voice'] if used_voice else []) + (['image'] if image_bytes else [])
    modality = '+'.join(modalities) or 'text'
    image_info = None
    if image_bytes is not None:
        try:
            image_info = analyze_image(image_bytes)
        except ValueError as exc:
            st.error(f'Image upload: {exc}')
            return
    intent = classify(text, history)
    metadata = {'modality':modality, 'image_name':image_name if image_bytes else '',
                'image_info':image_info or {}}
    store.add_message(cid, 'user', text, modality, metadata)

    has_reference = bool(re.search(r'\b(?:it|its|they|them|that|this|more)\b', text, flags=re.I))
    if intent.explanation == 'Resolved follow-up using conversation context.':
        context_used = 'A previous user turn resolved this follow-up through a local rule.'
    elif history and api_key() and not intent.requires_approval and (
            image_bytes is not None or local_response(intent, store, cid, history) is None):
        context_used = 'Recent conversation was supplied to the configured AI provider.'
    else:
        context_used = 'No prior context was used to resolve this command.'
        if has_reference and history:
            context_used += ' Offline rules did not resolve this reference.'
    extracted = {key:value for key, value in intent.data.items() if value is not None}
    trace = {
        'module_1':f'{modality} input standardized' + ('; OpenCV inspected image' if image_info else ''),
        'module_2':f'Intent: {intent.name}; {intent.explanation}',
        'entities':extracted,
        'keywords':[
            word for word in dict.fromkeys(re.findall(r"\b[\w'-]{3,}\b", text.lower()))
            if word not in {'the','and','for','with','what','this','that','please','about'}
        ][:8],
        'context_used':context_used,
        'module_3':'Awaiting confirmation' if intent.requires_approval else 'Read-only response; no external action',
    }
    if intent.requires_approval:
        if st.session_state.pending and st.session_state.pending['cid'] == cid:
            reply = 'Another action is awaiting confirmation. Approve or cancel it before requesting a new change.'
        else:
            proposal, error = prepare_proposal(intent, store, cid)
            if error:
                reply = f'⚠️ {error}'
            else:
                stage_action(proposal)
                details = proposal.data.get('text', '')
                reply = (f'**Approval required** — {ACTION_LABELS.get(proposal.name, proposal.name)}\n\n'
                         f'{details}\n\nReview the proposed operation below to confirm or cancel.')
    elif image_bytes is not None:
        if api_key():
            try:
                image_hash = hashlib.sha256(image_bytes).hexdigest()
                cached = st.session_state.get('vision_result', {}).get(image_hash)
                if cached and cached.get('question') == text:
                    reply = cached['description']
                else:
                    with st.spinner('Analyzing image with AI vision...'):
                        reply = ask_model(text, history, image_bytes, mime)
                    st.session_state.setdefault('vision_result', {})[image_hash] = {
                        'question': text,
                        'description': reply,
                        'cloud': True,
                        'metrics': image_info,
                    }
            except Exception as exc:
                reply = f'**Cloud vision unavailable:** {exc}\n\n**OpenCV-only fallback:**\n\n' + image_report(image_info)
                st.session_state.setdefault('vision_result', {})[image_hash if 'image_hash' in locals() else hashlib.sha256(image_bytes).hexdigest()] = {
                    'question': text,
                    'description': reply,
                    'cloud': False,
                    'metrics': image_info,
                }
        else:
            reply = '**OpenCV-only fallback:** cloud vision is unavailable because no AI API key is configured.\n\n' + image_report(image_info)
            image_hash = hashlib.sha256(image_bytes).hexdigest()
            st.session_state.setdefault('vision_result', {})[image_hash] = {
                'question': text,
                'description': reply,
                'cloud': False,
                'metrics': image_info,
            }
    else:
        answer = local_response(intent, store, cid, history)
        if answer is not None:
            reply = answer
        elif api_key():
            try:
                reply = ask_model(text, history)
            except Exception as exc:
                reply = f'AI service unavailable: {exc}\n\nTry a supported offline command, or check your key and connection.'
        elif intent.name == 'follow_up':
            reply = ('I recognized this as a **follow-up**, but offline rules cannot reliably resolve the reference '
                     'or generate an open-ended answer. Configure an AI API key to use recent messages for follow-up reasoning.')
        else:
            reply = ('I received your request and classified it as a **general question**, but open-ended '
                     'answers require an AI API key.\n\nThe **offline demo** can manage approved local tasks '
                     'and notes, calculate expressions, explain the three capstone modules, and inspect image properties. '
                     'Type `help` to see examples.')
    store.add_message(cid, 'assistant', reply, metadata={'intent':intent.name,
                                                       'reason':intent.explanation, 'trace':trace})
    st.rerun()


with st.sidebar:
    st.markdown('<div class="brand"><span class="brandmark">✦</span>IntentWeave</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtle" style="padding-left:51px">Context-aware AI workspace</div>', unsafe_allow_html=True)
    st.write('')
    st.caption('● AI CONNECTED' if api_key() else '● LOCAL DEMO MODE')
    if not api_key():
        st.caption('AI API key optional — see Settings')
    st.divider()
    st.radio('NAVIGATION', ['Home', 'AI Assistant', 'Multimodal Input', 'Context Memory',
                            'Action Center', 'Analytics', 'Demo Mode', 'About Project', 'Settings'],
             key='nav_radio', index=['Home', 'AI Assistant', 'Multimodal Input', 'Context Memory',
                                     'Action Center', 'Analytics', 'Demo Mode', 'About Project', 'Settings'].index(
                                         st.session_state.section),
             on_change=on_nav_change, label_visibility='collapsed')
    st.divider()
    if st.button('＋ New conversation', use_container_width=True, type='primary'):
        st.session_state.conversation_id = store.start_conversation(owner_id=owner_id)
        st.session_state.pending = None
        st.rerun()
    st.markdown('<div class="section-label">Recent conversations</div>', unsafe_allow_html=True)
    for convo in store.conversations(owner_id)[:7]:
        title = convo['title'].replace('\n',' ').strip()[:28]
        label = ('◆ ' if convo['id'] == cid else '○ ') + title
        if st.button(label, key=f"select_{convo['id']}", use_container_width=True):
            st.session_state.conversation_id = convo['id']
            st.session_state.pending = None
            st.rerun()
    st.write('')
    st.divider()
    st.caption('CSA1719 • Artificial Intelligence')
    st.caption('Student capstone implementation')


if st.session_state.section == 'Home':
    st.markdown('''<div class="hero">
      <div class="eyebrow">CSA1719 • ARTIFICIAL INTELLIGENCE CAPSTONE</div>
      <h1>IntentWeave AI</h1>
      <p>A context-aware multimodal assistant that turns text, voice, and image input into understandable intents
      and safely approved local actions.</p>
      <span class="pill">Multimodal input</span><span class="pill">Context-aware reasoning</span>
      <span class="pill">Verified local actions</span>
    </div>''', unsafe_allow_html=True)
    show_metrics()
    st.write('')
    st.markdown('### Processing pipeline')
    stages = [
        ('01 · RECOGNIZE','Text • Voice • Image','Standardize an input and measure image properties locally.'),
        ('02 · REASON','Intent • Context','Classify the request and use recent conversation where available.'),
        ('03 · VERIFY','Approval • SQLite','Review proposed changes before saving tasks or notes.'),
    ]
    for col, (number, title, description) in zip(st.columns(3), stages):
        with col:
            st.markdown(f'<div class="step"><div class="num">{number}</div><div class="heading">{title}</div>'
                        f'<div class="desc">{description}</div></div>', unsafe_allow_html=True)
    st.write('')
    a, b, c = st.columns(3)
    for col, label, page in ((a, 'Open AI Assistant', 'AI Assistant'),
                             (b, 'Try the guided demo', 'Demo Mode'),
                             (c, 'Review analytics', 'Analytics')):
        with col:
            if st.button(label, key=f'home_{page}', use_container_width=True):
                navigate(page)
                st.rerun()
    st.caption('Offline features include local intent rules, arithmetic, image measurements, conversation memory, and approved SQLite actions. Open-ended AI, visual Q&A, and cloud transcription need an API key and network access.')

elif st.session_state.section in ('AI Assistant', 'Multimodal Input'):
    st.markdown('''<div class="hero">
      <div class="eyebrow">✦ Multimodal intelligence • Powered by context</div>
      <h1>One assistant. Every way you communicate.</h1>
      <p>Ask a question, record your voice, or add an image. IntentWeave interprets your command,
         remembers the current conversation, and asks permission before changing your workspace.</p>
      <span class="pill">▤ Text</span><span class="pill">◉ Voice</span>
      <span class="pill">▧ Images</span><span class="pill">✓ Human approval</span>
    </div>''', unsafe_allow_html=True)
    show_metrics()
    st.write('')
    st.markdown('### Your conversation')
    history = store.messages(cid)
    if not history:
        st.caption('Start with a suggested command, or enter your own below.')
        st.markdown('<div class="section-label">Try a sample</div>', unsafe_allow_html=True)
        prompts = [
            'What does Module 2 do?',
            'Add a task to prepare my AI presentation',
            'Calculate (125 + 75) / 4',
        ]
        boxes = st.columns(3)
        for col, prompt in zip(boxes, prompts):
            with col:
                if st.button(prompt, key='prompt_'+str(prompts.index(prompt)), use_container_width=True):
                    queue_command(prompt)
                    st.rerun()
    for item in history:
        avatar = '👤' if item['role'] == 'user' else '🤖'
        with st.chat_message(item['role'], avatar=avatar):
            st.markdown(item['content'])
            if item['role'] == 'user':
                try:
                    meta = json.loads(item['metadata'])
                    if meta.get('image_name'):
                        st.caption('📎 Image provided: '+meta['image_name']+' (original image not saved)')
                    if 'voice' in item['modality']:
                        st.caption('🎙️ Speech transcribed to text')
                except (KeyError, ValueError, TypeError):
                    pass
            else:
                try:
                    trace = json.loads(item['metadata']).get('trace', {})
                    if trace:
                        with st.expander('View 3-module processing trace'):
                            st.write('**1. Multimodal recognition:**', trace.get('module_1',''))
                            st.write('**2. Contextual reasoning:**', trace.get('module_2',''))
                            st.write('**Extracted entities:**', trace.get('entities') or 'None extracted by local rules.')
                            st.write('**Keywords:**', ', '.join(trace.get('keywords', [])) or 'None')
                            st.write('**Context used:**', trace.get('context_used',''))
                            st.write('**3. Verified execution:**', trace.get('module_3',''))
                except (ValueError, TypeError):
                    pass
                if item['content'].strip():
                    speak_response(item['content'])
    if st.session_state.pending:
        confirmation_ui()
    st.markdown('<div class="section-label">Send a multimodal command</div>', unsafe_allow_html=True)
    with st.expander('＋ Add image or voice input (optional)', expanded=st.session_state.section == 'Multimodal Input'):
        image_col, camera_col = st.columns(2)
        with image_col:
            upload = st.file_uploader('Upload an image', type=['png','jpg','jpeg'],
                                      help='JPG, JPEG, and PNG images up to 8 MB are supported.')
        with camera_col:
            camera = st.camera_input('Or capture using webcam')
        recording = st.audio_input('Or record your voice', help='Allow microphone access in your browser and operating-system privacy settings.')
    image_file = upload if upload is not None else camera
    image_bytes = image_file.getvalue() if image_file is not None else None
    mimetype = (image_file.type or 'image/jpeg') if image_file is not None else 'image/jpeg'
    if image_bytes is not None:
        try:
            mimetype = validate_image(image_bytes, mimetype, image_file.name or '')
            preview_info = analyze_image(image_bytes)
            st.image(image_bytes, caption=image_file.name or 'Camera capture', use_container_width=True)
            if 'vision_result' not in st.session_state:
                st.session_state.vision_result = {}
            image_hash = hashlib.sha256(image_bytes).hexdigest()
            vision_record = st.session_state.vision_result.get(image_hash)
            if vision_record:
                st.markdown('### AI Vision Analysis')
                if vision_record.get('cloud'):
                    st.markdown(vision_record['description'])
                else:
                    st.warning('**OpenCV-only fallback:** cloud vision is unavailable.')
                    st.markdown(vision_record['description'])
            elif not api_key():
                st.info('**AI Vision Analysis unavailable:** configure `OPENAI_API_KEY` in `.env` or Streamlit Secrets.')
            st.markdown('#### OpenCV Metrics')
            metric_a, metric_b, metric_c, metric_d = st.columns(4)
            metric_a.metric('Resolution', f"{preview_info['width']} × {preview_info['height']}")
            metric_b.metric('Brightness', f"{preview_info['brightness']} / 255")
            metric_c.metric('Color tendency', preview_info['dominant_tone'])
            metric_d.metric('Edge density', f"{preview_info['edge_density_pct']}%")
            st.caption('OpenCV metrics are measurements only and do not identify objects or people.')
        except ValueError as exc:
            st.error(f'Image upload: {exc}')
    with st.form('composer', clear_on_submit=True):
        prompt = st.text_area('Message', key='draft', placeholder='Ask anything about your project, or type “help”…', height=94)
        submitted = st.form_submit_button('✦ Analyze & respond', type='primary', use_container_width=True)
    if submitted:
        typed_text = bool(prompt.strip())
        voice_used = recording is not None
        if recording:
            try:
                transcription = transcribe_audio(recording.getvalue())
                if not transcription:
                    st.warning('No words were recognized in the recording.')
                else:
                    prompt = (prompt.strip() + '\n' + transcription).strip()
            except Exception as exc:
                st.error(str(exc))
                if not prompt.strip() and image_bytes is None:
                    st.stop()
                voice_used = False
        handle_message(prompt, image_bytes, image_file.name if image_file else '', mimetype, voice_used, typed_text)
    st.caption('Demo privacy: chat, tasks, and notes are saved in a local SQLite file. Uploaded image/audio bytes are not stored. Cloud features send the current request to the configured AI provider.')

elif st.session_state.section == 'Action Center':
    st.markdown('''<div class="hero"><div class="eyebrow">LOCAL ACTION CENTER</div>
     <h1>Tasks & notes</h1><p>All changes go through Module 3 verification and require your approval.</p></div>''', unsafe_allow_html=True)
    show_metrics()
    confirmation_ui()
    task_tab, note_tab, log_tab = st.tabs(['✓ Tasks', '▤ Notes', '⌁ Action history'])
    with task_tab:
        st.markdown('#### Your tasks')
        tasks = store.tasks(cid)
        if not tasks:
            st.info('No tasks yet. Use the assistant: “Add a task to finish my report”.')
        for task in tasks:
            col1, col2 = st.columns([5,1.3])
            with col1:
                st.markdown(f"{'✅' if task['done'] else '⬜'} **Task #{task['id']}**")
                st.write(task['title'])
            with col2:
                if not task['done'] and st.button('Complete', key=f"complete_{task['id']}",
                                                  disabled=bool(st.session_state.pending)):
                    requested = Intent('task_complete', 'Selected task from workspace.',
                                       {'task_id':task['id'], 'text':task['title']}, True)
                    stage_action(requested)
                    st.rerun()
            st.divider()
        with st.form('workspace_task_form', clear_on_submit=True):
            title = st.text_input('New task', placeholder='e.g. Prepare demo screenshots')
            add = st.form_submit_button('Propose task', disabled=bool(st.session_state.pending))
        if add and title.strip():
            if stage_action(Intent('task_add', 'Workspace task entry', {'text':title.strip()}, True)):
                st.rerun()
    with note_tab:
        st.markdown('#### Saved notes')
        notes = store.notes(cid)
        if not notes:
            st.info('No notes yet. Use “Save a note: Project meeting at 3 PM”.')
        for note in notes:
            with st.expander(f"Note #{note['id']} · {note['created_at']}"):
                st.write(note['body'])
        with st.form('workspace_note_form', clear_on_submit=True):
            note_text = st.text_area('New note', height=100)
            save_note = st.form_submit_button('Propose note', disabled=bool(st.session_state.pending))
        if save_note and note_text.strip():
            if stage_action(Intent('note_add', 'Workspace note entry', {'text':note_text.strip()}, True)):
                st.rerun()
    with log_tab:
        st.markdown('#### Action audit trail')
        actions = store.actions(cid)
        if not actions:
            st.info('The audit trail will show confirmed, canceled, and failed local operations.')
        for log in actions:
            st.markdown(f"**{log['action']}** — `{log['status']}`")
            st.caption(log['created_at'] + ' · ' + log['details'])
            st.divider()

elif st.session_state.section == 'Context Memory':
    st.markdown('''<div class="hero"><div class="eyebrow">SESSION CONTEXT</div>
      <h1>Context memory</h1><p>Review the saved messages available to the assistant for follow-up questions.
      Conversation history is local to this SQLite-backed session.</p></div>''', unsafe_allow_html=True)
    history = store.messages(cid)
    if not history:
        st.info('No conversation messages yet. Start a conversation in AI Assistant.')
    else:
        for item in history:
            with st.chat_message(item['role']):
                st.markdown(item['content'])
                if item['role'] == 'user':
                    st.caption(f"Input modality: {item['modality']} · {item['created_at']}")
    st.divider()
    st.markdown('#### Clear conversation history')
    st.caption('This removes messages, tasks, notes, and action logs from this conversation only.')
    confirm_clear = st.checkbox('I confirm that I want to clear this conversation.', key='confirm_clear_history')
    if st.button('Clear conversation history', type='secondary', disabled=not confirm_clear,
                 key='clear_history_button'):
        store.delete_conversation(cid)
        st.session_state.conversation_id = store.start_conversation(owner_id=owner_id)
        st.session_state.pending = None
        st.rerun()

elif st.session_state.section == 'Analytics':
    analytics = store.analytics(owner_id)
    st.markdown('''<div class="hero"><div class="eyebrow">ACTIVITY OVERVIEW</div>
      <h1>Usage analytics</h1><p>Counts below come from saved conversations, messages, and action logs in the local database.</p></div>''', unsafe_allow_html=True)
    metrics = st.columns(3)
    for column, value, label in zip(metrics,
            (analytics['commands'], analytics['completed_actions'], analytics['pending_approvals']),
            ('Processed commands', 'Completed actions', 'Pending approvals')):
        with column:
            st.markdown(f'<div class="metric"><div class="value">{value}</div><div class="name">{label}</div></div>',
                        unsafe_allow_html=True)
    modality_col, intent_col = st.columns(2)
    with modality_col:
        st.markdown('#### Input modality')
        st.bar_chart(analytics['modalities'] or {'No records': 0})
    with intent_col:
        st.markdown('#### Detected intent')
        st.bar_chart(analytics['intents'] or {'No records': 0})
    st.markdown('#### Recent action activity')
    if not analytics['recent_actions']:
        st.info('No saved action events yet.')
    else:
        for action in analytics['recent_actions']:
            st.markdown(f"**{action['action']}** · `{action['status']}`")
            st.caption(f"{action['created_at']} · {action['details']}")
    st.markdown('#### Recent interactions')
    for message in analytics['recent_messages']:
        st.markdown(f"**{message['role'].title()}** · {message['modality']} · {message['created_at']}")
        st.caption(message['content'][:240])

elif st.session_state.section == 'Demo Mode':
    st.markdown('''<div class="hero"><div class="eyebrow">FACULTY WALKTHROUGH · APPROX. 5 MINUTES</div>
      <h1>Guided demo mode</h1><p>Each prompt is routed through the real application. Sample buttons only populate the assistant;
      they do not simulate responses or save actions without your confirmation.</p></div>''', unsafe_allow_html=True)
    st.markdown('#### Start-to-finish walkthrough')
    demo_steps = [
        ('1 · Text command','Explain artificial intelligence in simple words.','AI Assistant'),
        ('2 · Context follow-up','Explain its applications.','AI Assistant'),
        ('3 · Voice input','Speak: “Create a task to submit my assignment tomorrow.”','Multimodal Input'),
        ('4 · Image input','Upload a photo and ask: “What is in this image?”','Multimodal Input'),
        ('5 · Verified action','Create a task called Prepare capstone presentation.','AI Assistant'),
        ('6 · Analytics','Review the activity recorded in the dashboard.','Analytics'),
    ]
    for title, detail, page in demo_steps:
        with st.container(border=True):
            st.markdown(f'**{title}**')
            st.write(detail)
            if title.startswith(('1 ·', '2 ·', '5 ·')):
                if st.button('Use this prompt', key=f'demo_{title}', use_container_width=False):
                    queue_command(detail)
                    navigate(page)
                    st.rerun()
            elif title.startswith(('3 ·', '4 ·')):
                if st.button('Open multimodal input', key=f'demo_{title}', use_container_width=False):
                    navigate(page)
                    st.rerun()
            elif st.button('Open analytics', key='demo_analytics'):
                navigate(page)
                st.rerun()
    st.markdown('#### What depends on what?')
    st.markdown('''
    - **Local:** text rule classification, arithmetic, recent conversation storage, OpenCV image measurements,
      SQLite tasks/notes, approvals, and analytics.
    - **Optional AI provider:** open-ended answers and semantic image questions; requires a valid `.env` API key,
      internet connectivity, model access, and may incur charges.
    - **Internet-dependent without an API key:** browser-recorded voice currently uses the configured transcription
      path or the optional Google speech-recognition service.
    - **No hidden demo data:** counters and charts read persisted records from the configured database.
    ''')

elif st.session_state.section == 'About Project':
    st.markdown('''<div class="hero"><div class="eyebrow">SYSTEM ARCHITECTURE</div>
       <h1>Three modules. One intelligent workflow.</h1>
       <p>IntentWeave AI: A Context-Aware Multimodal Assistant · Course: CSA1719 Artificial Intelligence.</p></div>''', unsafe_allow_html=True)
    stages = [
        ('MODULE 01 • INPUT','Multimodal Command Recognition',
         'Text input, microphone recording with speech-to-text, image uploads or webcam, and local OpenCV image measurements.'),
        ('MODULE 02 • REASON','Contextual Intent Reasoning',
         'Keyword and pattern classification, follow-up references to recent messages, and optional model-powered replies.'),
        ('MODULE 03 • ACT','Verified Action Execution',
         'Validate proposed task/note operations, request confirmation, execute approved changes, and keep an audit trail.'),
    ]
    for col, (num, heading, desc) in zip(st.columns(3), stages):
        with col:
            st.markdown(f'<div class="step"><div class="num">{num}</div><div class="heading">{heading}</div>'
                        f'<div class="desc">{desc}</div></div>', unsafe_allow_html=True)
    st.write('')
    st.markdown('#### Processing pipeline')
    st.code('Text / Voice / Image\n         ↓\nInput standardization + OpenCV / transcription\n         ↓\nRule-based intent + recent conversation context\n         ↓\nRead-only reply   OR   proposed local action\n                              ↓\n                      User confirmation\n                              ↓\n                      SQLite + audit log', language='text')
    st.markdown('#### Aim and objectives')
    st.write('**Aim:** demonstrate a context-aware assistant that can interpret multiple input types and safely handle supported local actions.')
    st.write('**Problem statement:** common assistant interfaces often separate text, voice, and visual inputs from conversational context, while actions can modify data without a clear review step. This prototype demonstrates a unified local workflow with context visibility and explicit approval for supported changes.')
    st.markdown('''
    - Recognize text, voice recordings, and uploaded images.
    - Classify useful intents and maintain recent conversation context.
    - Require user approval before changing saved tasks or notes.
    - Record conversations and actions locally for review and analytics.
    ''')
    st.markdown('#### Technologies')
    st.write('Python, Streamlit, SQLite, OpenCV, NumPy, Requests, python-dotenv, and optional OpenAI-compatible chat/transcription APIs.')
    st.markdown('#### Processing flow')
    st.code('Text / Voice / Image -> Input Processing -> Multimodal Fusion -> Intent Detection -> Context Memory -> Verified Action Execution -> Output', language='text')
    st.markdown('#### Advantages, applications, and limitations')
    st.write('The prototype combines familiar input modes, explains its local reasoning path, supports educational task/note workflows, and keeps changes approval-gated. It is a single-user academic demo; rule-based intent handling is limited, AI and cloud transcription depend on external services, OpenCV measurements do not identify objects, and it does not authenticate users or execute arbitrary system actions.')
    st.markdown('#### Future scope')
    st.write('Potential future work includes broader validated intent coverage, accessibility improvements, stronger privacy controls, and evaluation against a labeled dataset. No external actions are claimed by this implementation.')
    st.info('No student or faculty names are included. No presentation file was present in the inspected project workspace; the module terminology follows the existing project documentation and implementation.')

else:  # Settings
    st.markdown('''<div class="hero"><div class="eyebrow">SETTINGS & PRIVACY</div>
      <h1>Configuration & local data</h1><p>Understand what is enabled, export your conversation, or remove a conversation and its workspace.</p></div>''', unsafe_allow_html=True)
    st.markdown('#### AI connectivity')
    if api_key():
        st.success('OPENAI_API_KEY detected. AI conversation, visual Q&A and voice transcription are enabled (network and account access required).')
    else:
        st.warning('No OPENAI_API_KEY configured. The application runs in limited offline mode; free Google-based speech recognition still needs internet access.')
    st.markdown('To enable AI features, copy `.env.example` to `.env`, set `OPENAI_API_KEY`, and restart Streamlit. Never paste an API key into a chat message.')
    st.markdown('#### Data export')
    st.download_button('↓ Export current conversation (JSON)', data=store.export_conversation(cid),
                       file_name='intentweave_conversation.json', mime='application/json')
    st.markdown('#### Remove conversation')
    st.caption('Deletes this conversation and associated tasks, notes, messages, and logs from the local SQLite database. This cannot be undone.')
    agree = st.checkbox('I understand that this deletes the selected conversation.')
    if st.button('Delete this conversation', disabled=not agree):
        store.delete_conversation(cid)
        other = store.conversations(owner_id)
        st.session_state.conversation_id = other[0]['id'] if other else store.start_conversation(owner_id=owner_id)
        st.session_state.pending = None
        st.rerun()
    st.divider()
    st.caption('Intended for coursework and local demonstrations, not multi-user production use. Secure authentication, encrypted storage, rate limits and a production deployment review would be needed before public release.')
