import streamlit as st
import json
import random
from groq import Groq

# --- CONFIGURATION ---
# Accesses your secret key from the Streamlit Cloud dashboard
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# --- FUNCTIONS ---
@st.cache_data
def load_data():
    with open('rules.json', 'r') as file:
        return json.load(file)

def clean_json(text):
    """Safety feature: Removes markdown formatting if the AI includes it"""
    text = text.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[1]
        if text.endswith('```'):
            text = text.rsplit('\n', 1)[0]
    return json.loads(text)

def evaluate_answer(original, target_rule, student_answer):
    """Smarter, encouraging evaluation using Llama 3.3 70B"""
    prompt = f"""
    You are a helpful and encouraging English Grammar Tutor.
    Rule: {target_rule}
    Original Sentence: "{original}"
    Student's Answer: "{student_answer}"

    EVALUATION CRITERIA:
    1. Did they follow the specific transformation rule?
    2. Did they keep the original meaning?
    3. Are there minor typos? (Be lenient on one small typo, but strict on grammar).

    If the answer is logically correct but doesn't follow the formal rule perfectly, 
    mark it as 'is_correct': false but give feedback that is encouraging, 
    explaining why the formal rule is different.

    Respond STRICTLY in valid JSON:
    {{"is_correct": true, "feedback": "Your encouraging explanation here."}}
    """
    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.3-70b-versatile",
        response_format={"type": "json_object"}
    )
    return json.loads(chat_completion.choices[0].message.content)

def generate_new_question(rule_desc, category, examples, current_sentence):
    """Generates a highly creative new question with forced variety."""
    
    # 1. Define the possible directions
    if "Simple, Complex" in category:
        types = ["Simple", "Complex", "Compound"]
    elif "Affirmative" in category:
        types = ["Affirmative", "Negative"]
    elif "Exclamatory" in category:
        types = ["Assertive", "Exclamatory"]
    elif "Interrogative" in category:
        types = ["Assertive", "Interrogative"]
    elif "Degree" in category:
        types = ["Positive", "Comparative", "Superlative"]
    elif "Imperative" in category:
        types = ["Assertive", "Imperative"]
    else:
        types = ["Original", "Converted"]

    # 2. Pick the transformation direction
    source, target = random.sample(types, 2)
    forced_instruction = f"Convert this {source} sentence to {target}."

    # 3. Pick a random theme to force creativity
    themes = [
        "Deep Sea Exploration", "Cyberpunk Future", "Medieval Fantasy", 
        "Cooking/Kitchen", "Space Travel", "Time Travel", "Detective Mystery", 
        "Modern Technology", "Ancient Egypt", "Olympic Sports"
    ]
    random_theme = random.choice(themes)

    prompt = f"""
    You are an expert English Grammar Test Creator.
    Rule to follow: "{rule_desc}"
    
    TASK: Generate a unique grammar question.
    REQUIRED DIRECTION: {forced_instruction}
    THEME/CONTEXT: {random_theme}
    
    CRITICAL CREATIVITY RULES:
    1. DO NOT use these words/topics from the examples: {examples}
    2. DO NOT use the current sentence: "{current_sentence}"
    3. The sentence MUST be about "{random_theme}".
    4. Use interesting, natural vocabulary. Avoid "The boy runs" level sentences.
    5. Ensure the 'original' is a perfect example of a {source} sentence.
    6. Ensure the 'converted' is the perfect {target} version of it.
    
    Respond ONLY in JSON:
    {{
        "instruction": "{forced_instruction}",
        "original": "...",
        "converted": "..."
    }}
    """
    
    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.3-70b-versatile",
        response_format={"type": "json_object"},
        temperature=1.0 # Keep it high for creativity
    )
    return json.loads(chat_completion.choices[0].message.content)

# --- DATA LOADING ---
data = load_data()

# --- STATE MANAGEMENT ---
def pick_new_rule():
    if 'history' not in st.session_state:
        st.session_state.history = []

    # Pick a random category and rule
    category = random.choice(data['transformation_categories'])
    rule = random.choice(category['rules'])
    
    # Try to pick an example that isn't in recent history
    example = random.choice(rule['examples'])
    for _ in range(5): 
        if example['original'] in st.session_state.history:
            example = random.choice(rule['examples'])
        else:
            break

    # Update history tracking
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
        st.session_state.category,
        st.session_state.examples,
        st.session_state.original_sentence
    )
    st.session_state.instruction = new_q.get('instruction', 'Convert this sentence:')
    st.session_state.original_sentence = new_q['original']
    st.session_state.correct_example = new_q['converted']
    st.session_state.evaluated = False
    st.session_state.user_answer = ""

# Initialization
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

# Heading 3 makes the sentence bold and clean without the gray blockquote
st.markdown(f"### {st.session_state.original_sentence}") 
st.write("")

# Form for submission
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
                        st.error(f"Error: {e}")
            else:
                st.warning("Please type an answer first.")

# Result Display
if st.session_state.evaluated:
    st.markdown(f"**Your Answer:** {st.session_state.user_answer}")
    
    result = st.session_state.evaluation_result
    
    if result['is_correct']:
        st.success(f"**✅ Correct!** {result['feedback']}")
    else:
        st.error(f"**❌ Not quite.** {result['feedback']}")
        st.warning(f"**One valid answer:** {st.session_state.correct_example}")
    
    st.markdown("---")
    
    # Action Buttons
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