import streamlit as st
import json
import random
import google.generativeai as genai

# --- CONFIGURATION ---
API_KEY = st.secrets["GOOGLE_API_KEY"] 
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# --- FUNCTIONS ---
@st.cache_data
def load_data():
    with open('rules.json', 'r') as file:
        return json.load(file)

def clean_json(text):
    """Safety feature: Removes markdown formatting if the AI accidentally includes it"""
    text = text.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[1]
        if text.endswith('```'):
            text = text.rsplit('\n', 1)[0]
    return json.loads(text)

def evaluate_answer(original, target_rule, student_answer):
    """Evaluates if the student applied the rule correctly."""
    prompt = f"""
    You are an expert, strict English grammar examiner. 
    Original Sentence: "{original}"
    Target Transformation Rule: "{target_rule}"
    Student's Answer: "{student_answer}"
    
    Did the Student successfully apply the rule and maintain the exact meaning of the Original Sentence?
    Respond STRICTLY in valid JSON format:
    {{"is_correct": true, "feedback": "1-2 sentence explanation."}}
    """
    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(response_mime_type="application/json")
    )
    return clean_json(response.text)

def generate_new_question(rule_desc, examples):
    """Generates a brand new sentence testing the exact same rule."""
    prompt = f"""
    You are an expert English test creator. 
    Rule to test: "{rule_desc}"
    Examples of this rule: {examples}
    
    Generate ONE brand new, unique sentence that tests this exact rule.
    Do NOT copy the examples. Use different vocabulary.
    
    Respond STRICTLY in valid JSON format with three keys: 'instruction', 'original', and 'converted'.
    Example format:
    {{"instruction": "Convert this Simple sentence to Complex.", "original": "The new sentence to convert", "converted": "The correct converted answer"}}
    """
    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(response_mime_type="application/json")
    )
    return clean_json(response.text)

# --- STATE MANAGEMENT ---
data = load_data()

def pick_new_rule():
    category = random.choice(data['transformation_categories'])
    rule = random.choice(category['rules'])
    example = random.choice(rule['examples'])
    
    st.session_state.category = category['category_name']
    st.session_state.rule_desc = rule['rule_description']
    st.session_state.examples = rule['examples']
    st.session_state.instruction = example.get('instruction', 'Convert this sentence according to the rule:') 
    st.session_state.original_sentence = example['original']
    st.session_state.correct_example = example['converted']
    st.session_state.evaluated = False
    st.session_state.user_answer = ""

def generate_same_rule():
    new_q = generate_new_question(st.session_state.rule_desc, st.session_state.examples)
    st.session_state.instruction = new_q.get('instruction', 'Convert this sentence:')
    st.session_state.original_sentence = new_q['original']
    st.session_state.correct_example = new_q['converted']
    st.session_state.evaluated = False
    st.session_state.user_answer = ""

if 'rule_desc' not in st.session_state:
    pick_new_rule()

# --- USER INTERFACE ---
st.title("🎯 Grammar: Learning by Doing")

# Better Formatting for Reading / Printing
st.markdown(f"### Topic: {st.session_state.category}")

st.markdown("---")
st.markdown("#### 📖 The Rule to Apply:")
st.info(f"**{st.session_state.rule_desc}**")
st.markdown("---")

st.markdown("#### ✍️ Your Task:")
st.markdown(f"**{st.session_state.instruction}**")
st.write("") # Adds a little breathing room
st.markdown(f"### {st.session_state.original_sentence}") # ### makes it larger, bolder, and not gray
st.write("")

# Input Box (Wrapped in a form for stability)
if not st.session_state.evaluated:
    with st.form("answer_form"):
        user_input = st.text_input("Type your converted sentence here:")
        submitted = st.form_submit_button("Submit Answer")
        
        if submitted:
            if user_input:
                with st.spinner("AI is grading your answer..."):
                    try:
                        result = evaluate_answer(
                            st.session_state.original_sentence, 
                            st.session_state.rule_desc, 
                            user_input
                        )
                        st.session_state.evaluation_result = result
                        st.session_state.user_answer = user_input
                        st.session_state.evaluated = True
                        st.rerun() # Refresh page
                    except Exception as e:
                        st.error(f"Network error, please try submitting again. (Details: {e})")
            else:
                st.warning("Please type an answer first.")

# Results & Next Steps
if st.session_state.evaluated:
    st.markdown(f"**Your Answer:** {st.session_state.user_answer}")
    
    result = st.session_state.evaluation_result
    
    # Show Grade
    if result['is_correct']:
        st.success(f"**✅ Correct!** {result['feedback']}")
    else:
        st.error(f"**❌ Not quite.** {result['feedback']}")
        st.warning(f"**One valid answer:** {st.session_state.correct_example}")
    
    st.markdown("---")
    
    # Mastery Buttons side-by-side
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Try Another (Same Rule)", use_container_width=True):
            with st.spinner("Generating new question..."):
                generate_same_rule()
                st.rerun()
    with col2:
        # Highlight the comfy button
        if st.button("✅ I'm Comfortable (Next Rule)", type="primary", use_container_width=True):
            pick_new_rule()
            st.rerun()