import streamlit as st
import json
import random
from groq import Groq

# --- CONFIGURATION ---
# Pulls from Streamlit Cloud Secrets
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# --- FUNCTIONS ---
@st.cache_data
def load_data():
    with open('rules.json', 'r') as file:
        return json.load(file)

def clean_json(text):
    """Removes markdown formatting if the AI includes it"""
    text = text.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[1]
        if text.endswith('```'):
            text = text.rsplit('\n', 1)[0]
    return json.loads(text)

def evaluate_answer(original, target_rule, student_answer):
    """Evaluates the student's answer using Groq (Llama 3.3)"""
    prompt = f"""
    You are a helpful and encouraging English Grammar Tutor.
    Task: {target_rule}
    Original: "{original}"
    Student's Answer: "{student_answer}"

    EVALUATION CRITERIA:
    1. Did they follow the specific transformation rule?
    2. Did they keep the original meaning?
    3. Are there minor typos? (Be lenient on one small typo, but strict on grammar).

    Respond STRICTLY in valid JSON:
    {{"is_correct": true, "feedback": "Your encouraging explanation here."}}
    """
    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.3-70b-versatile",
        response_format={"type": "json_object"}
    )
    return json.loads(chat_completion.choices[0].message.content)

def generate_new_question(rule_desc, examples, current_sentence):
    """Generates a new question and avoids the current one."""
    prompt = f"""
    You are an expert English test creator. 
    Rule to test: "{rule_desc}"
    Examples of this rule: {examples}
    
    CRITICAL: Do NOT generate this sentence: "{current_sentence}"
    Generate a BRAND NEW, unique sentence using different nouns and verbs.
    
    Respond STRICTLY in valid JSON format:
    {{"instruction": "Convert this sentence...", "original": "...", "converted": "..."}}
    """
    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.3-70b-versatile",
        response_format={"type": "json_object"},
        temperature=0.9 
    )
    return json.loads(chat_completion.choices[0].message.content)

# --- DATA LOADING & STATE MANAGEMENT ---
# THE FIX: This line must exist here so all functions can see 'data'
data = load_data()

def pick_new_rule():
    if 'history' not in st.session_state:
        st.session_state.history = []

    # Pick a random rule
    category = random.choice(data['transformation_categories'])
    rule = random.choice(category['rules'])
    
    # Try to pick an example that isn't in recent history
    example = random.choice(rule['examples'])
    for _ in range(5): 
        if example['original'] in st.session_state.history:
            example = random.choice(rule['examples'])
        else:
            break

    # Update History
    st.session_state.history.append(example['original'])
    if len(st.session_state.history) > 10:
        st.session_state.history.pop(0)

    st.session_state.category = category['category_name']
    st.session_state.rule_desc = rule['rule_description']
    st.session_state.examples = rule['examples']
    st.session_state.instruction = example.get('instruction', 'Convert this sentence:') 
    st.session_state.original_sentence = example['original']
    st.session_state.correct_example = example['converted']
    st.session_state.evaluated = False
    st.session_state.user_answer = ""

def generate_same_rule():
    new_q = generate_new_question(
        st.session_state.rule_desc, 
        st.session_state.examples,
        st.session_state.original_sentence
    )
    st.session_state.instruction = new_q.get('instruction', 'Convert this sentence:')
    st.session_state.original_sentence = new_q['original']
    st.session_state.correct_example = new_q['converted']
    st.session_state.evaluated = False
    st.session_state.user_answer = ""

# Start the app logic
if 'rule_desc' not in st.session_state:
    pick_new_rule()

# --- USER INTERFACE ---
st.title("🎯 Grammar: Learning by Doing")
st.markdown(f"### Topic: {st.session_state.category}")
st.markdown("---")
st.markdown("#### 📖 The Rule to Apply:")
st.info(f"**{st.session_state.rule_desc}**")
st.markdown("---")
st.markdown("#### ✍️ Your Task:")
st.markdown(f"**{st.session_state.instruction}**")
st.write("") 
st.markdown(f"### {st.session_state.original_sentence}") 
st.write("")

if not st.session_state.evaluated:
    with st.form("answer_form"):
        user_input = st.text_input("Type your converted sentence here:")
        submitted = st.form_submit_button("Submit Answer")
        
        if submitted:
            if user_input:
                with st.spinner("AI is grading..."):
                    try:
                        result = evaluate_answer(
                            st.session_state.original_sentence, 
                            st.session_state.rule_desc, 
                            user_input
                        )
                        st.session_state.evaluation_result = result
                        st.session_state.user_answer = user_input
                        st.session_state.evaluated = True
                        st.rerun()
                    except Exception as e:
                        st.error(f"AI Error. Please try again. (Details: {e})")
            else:
                st.warning("Please type an answer first.")

if st.session_state.evaluated:
    st.markdown(f"**Your Answer:** {st.session_state.user_answer}")
    result = st.session_state.evaluation_result
    if result['is_correct']:
        st.success(f"**✅ Correct!** {result['feedback']}")
    else:
        st.error(f"**❌ Not quite.** {result['feedback']}")
        st.warning(f"**One valid answer:** {st.session_state.correct_example}")
    
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Try Another (Same Rule)", use_container_width=True):
            with st.spinner("Generating..."):
                generate_same_rule()
                st.rerun()
    with col2:
        if st.button("✅ I'm Comfortable (Next Rule)", type="primary", use_container_width=True):
            pick_new_rule()
            st.rerun()