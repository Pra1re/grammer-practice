import streamlit as st
import json
import random
from groq import Groq

# --- CONFIGURATION ---
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# --- FUNCTIONS ---
@st.cache_data
def load_data():
    """Load and validate the JSON rules file."""
    try:
        with open('rules.json', 'r', encoding='utf-8') as file:
            data = json.load(file)
        
        # Validate structure
        if 'transformation_categories' not in data:
            st.error("Invalid JSON: Missing 'transformation_categories'")
            st.stop()
        
        for cat in data['transformation_categories']:
            if 'rules' not in cat:
                st.error(f"Category '{cat.get('category_name', 'Unknown')}' missing 'rules'")
                st.stop()
            for rule in cat['rules']:
                if 'examples' not in rule:
                    st.error(f"Rule '{rule.get('rule_description', 'Unknown')}' missing 'examples'")
                    st.stop()
                if not rule['examples']:
                    st.error(f"Rule '{rule.get('rule_description', 'Unknown')}' has empty examples")
                    st.stop()
        
        return data
    except FileNotFoundError:
        st.error("rules.json file not found! Please ensure it exists in the same directory.")
        st.stop()
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON format in rules.json: {str(e)}")
        st.stop()

def clean_json(text):
    """Clean JSON response from LLM."""
    text = text.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[1]
        if text.endswith('```'):
            text = text.rsplit('\n', 1)[0]
    return json.loads(text)

def evaluate_answer(original, target_rule, student_answer):
    """Few-shot reasoning evaluation with error handling."""
    prompt = f"""
    You are an expert English Grammar Tutor.
    
    Task: Apply the rule: "{target_rule}"
    
    Original sentence: "{original}"
    
    Student's answer: "{student_answer}"
    
    Evaluate:
    1. Did they correctly apply the transformation rule?
    2. Is the grammatical meaning identical to the original?
    3. Is the sentence natural and correct English?
    
    Be lenient on punctuation and capitalization, but strict on grammar.
    
    Respond STRICTLY in this JSON format:
    {{"is_correct": true, "feedback": "Explanation of why it's correct or what needs fixing."}}
    """
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=300
        )
        return json.loads(chat_completion.choices[0].message.content)
    except Exception as e:
        st.error(f"Evaluation error: {str(e)}")
        return {"is_correct": False, "feedback": "System error. Please try again."}

def generate_new_question(rule_desc, category, examples, current_sentence):
    """Generates unique questions with themes."""
    
    # Determine transformation types based on category name
    category_lower = category.lower()
    
    if "interrogative" in category_lower:
        if "affirmative" in category_lower:
            types = ["Affirmative", "Interrogative"]
        else:
            types = ["Assertive", "Interrogative"]
    elif "negative" in category_lower:
        types = ["Affirmative", "Negative"]
    elif "exclamatory" in category_lower:
        types = ["Assertive", "Exclamatory"]
    elif "compound" in category_lower:
        types = ["Simple", "Compound", "Complex"]
    elif "complex" in category_lower:
        types = ["Simple", "Complex"]
    elif "assertive" in category_lower and "imperative" in category_lower:
        types = ["Assertive", "Imperative"]
    elif "simple" in category_lower:
        types = ["Simple", "Complex", "Compound"]
    else:
        # Fallback: try to extract from category name like "Affirmative to Negative"
        if " to " in category:
            parts = category.split(" to ")
            if len(parts) == 2:
                types = parts
            else:
                types = ["Original", "Converted"]
        else:
            types = ["Original", "Converted"]
    
    # Ensure we have at least 2 different types
    if len(types) < 2:
        types = ["Original", "Converted"]
    
    source, target = random.sample(types, 2)
    forced_instruction = f"Convert this {source} sentence to {target}."
    
    themes = ["Cyberpunk", "Space Exploration", "Medieval Castle", "Deep Sea", "Time Travel", "Artificial Intelligence", "Climate Change", "Ancient Civilization"]
    
    prompt = f"""
    Rule: {rule_desc}. 
    Direction: {forced_instruction}. 
    Theme: {random.choice(themes)}.
    
    Generate a brand new, natural English sentence on that theme.
    The sentence must be different from: {current_sentence}
    The sentence should be appropriate for the transformation rule.
    
    Return ONLY valid JSON (no markdown, no extra text):
    {{"instruction": "{forced_instruction}", "original": "...", "converted": "..."}}
    """
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"},
            temperature=1.0,
            max_tokens=200
        )
        result = json.loads(chat_completion.choices[0].message.content)
        
        # Validate the result has required fields
        if 'original' not in result or 'converted' not in result:
            raise ValueError("Generated response missing required fields")
        
        return result
    except Exception as e:
        st.warning(f"Could not generate new question: {str(e)}. Using fallback.")
        # Fallback: return a random existing example
        if examples:
            example = random.choice(examples)
            return {
                "instruction": example.get('instruction', forced_instruction),
                "original": example['original'],
                "converted": example['converted']
            }
        else:
            # Ultimate fallback
            return {
                "instruction": forced_instruction,
                "original": "The student studies regularly.",
                "converted": "The student who studies regularly can expect success."
            }

# --- DATA LOADING ---
data = load_data()

# Calculate total rules for progress tracking
total_rules = sum(len(cat['rules']) for cat in data['transformation_categories'])

# --- STATE MANAGEMENT ---
def pick_new_rule():
    """Pick a new rule not in blacklist."""
    # Initialize session state lists
    if 'blacklist' not in st.session_state: 
        st.session_state.blacklist = []
    if 'history' not in st.session_state: 
        st.session_state.history = []

    # Get all rules from all categories
    all_available_rules = []
    for cat in data['transformation_categories']:
        for rule in cat['rules']:
            # Only add rules not in the blacklist
            if rule['rule_description'] not in st.session_state.blacklist:
                all_available_rules.append((cat['category_name'], rule))

    # Check if we ran out of rules
    if not all_available_rules:
        st.session_state.mastered_all = True
        return

    # Randomly pick from the remaining pool
    category_name, rule = random.choice(all_available_rules)
    example = random.choice(rule['examples'])
    
    # Handle instruction field (use default if missing)
    instruction = example.get('instruction', f"Convert this sentence according to the rule above:")
    
    # Update session state
    st.session_state.category = category_name
    st.session_state.rule_desc = rule['rule_description']
    st.session_state.examples = rule['examples']
    st.session_state.instruction = instruction
    st.session_state.original_sentence = example['original']
    st.session_state.correct_example = example['converted']
    st.session_state.evaluated = False
    st.session_state.user_answer = ""
    st.session_state.mastered_all = False

def generate_same_rule():
    """Generate a new question for the current rule."""
    new_q = generate_new_question(
        st.session_state.rule_desc, 
        st.session_state.category, 
        st.session_state.examples, 
        st.session_state.original_sentence
    )
    st.session_state.instruction = new_q.get('instruction', f"Convert this sentence:")
    st.session_state.original_sentence = new_q['original']
    st.session_state.correct_example = new_q['converted']
    st.session_state.evaluated = False
    st.session_state.user_answer = ""

# Initialization (only if not already initialized)
if 'rule_desc' not in st.session_state:
    pick_new_rule()

# --- USER INTERFACE ---
st.set_page_config(page_title="Grammar Master", page_icon="🎯", layout="wide")

st.title("🎯 Grammar Master - Sentence Transformation")
st.markdown("Master English sentence transformations with AI-powered feedback!")

# Handle the "Winner" screen
if st.session_state.get('mastered_all'):
    st.balloons()
    st.success("### 🎉 Incredible! You've mastered every rule in this session!")
    st.markdown("You've demonstrated expertise in all sentence transformation categories.")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Reset Blacklist & Start Over", type="primary"):
            st.session_state.blacklist = []
            st.session_state.history = []
            pick_new_rule()
            st.rerun()
    with col2:
        if st.button("📊 View Statistics"):
            st.json({
                "Total Rules Mastered": len(st.session_state.blacklist),
                "Total Rules Available": total_rules,
                "Completion Rate": f"{len(st.session_state.blacklist)/total_rules*100:.1f}%"
            })
    st.stop()

# Progress Bar
if total_rules > 0:
    progress_value = len(st.session_state.get('blacklist', [])) / total_rules
    st.write(f"### Session Progress: {len(st.session_state.blacklist)} / {total_rules} rules mastered")
    st.progress(progress_value)
    
    # Optional: Show remaining rules count
    remaining = total_rules - len(st.session_state.blacklist)
    if remaining > 0:
        st.caption(f"🎯 {remaining} more rules to master!")

st.divider()

# Main content area
col1, col2 = st.columns([2, 1])

with col1:
    st.markdown(f"### 📚 Current Topic")
    st.info(f"**Category:** {st.session_state.category}")
    
    with st.expander("📖 View Rule Explanation", expanded=False):
        st.markdown(f"**Rule:** {st.session_state.rule_desc}")
        st.markdown("---")
        st.markdown("**Example transformations from this rule:**")
        for i, ex in enumerate(st.session_state.examples[:3], 1):
            st.markdown(f"{i}. **Original:** {ex['original']}")
            st.markdown(f"   **Converted:** {ex['converted']}")

with col2:
    st.metric("Rules Mastered", len(st.session_state.blacklist), 
              delta=f"{len(st.session_state.blacklist)}/{total_rules}")

st.divider()

# Question section
st.markdown(f"### ✍️ Your Challenge")
st.markdown(f"**{st.session_state.instruction}**")
st.markdown(f"### 📝 {st.session_state.original_sentence}")

# Answer input area
if not st.session_state.evaluated:
    with st.form(key="answer_form"):
        user_input = st.text_area("Your answer:", height=100, placeholder="Type your transformed sentence here...")
        
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            submitted = st.form_submit_button("🚀 Submit Answer", type="primary", use_container_width=True)
        with col2:
            if st.form_submit_button("🔄 Skip to Next Rule", use_container_width=True):
                st.session_state.blacklist.append(st.session_state.rule_desc)
                pick_new_rule()
                st.rerun()
        
        if submitted:
            if user_input.strip():
                with st.spinner("🤖 Grading your answer..."):
                    res = evaluate_answer(st.session_state.original_sentence, st.session_state.rule_desc, user_input)
                    st.session_state.evaluation_result = res
                    st.session_state.user_answer = user_input
                    st.session_state.evaluated = True
                    st.rerun()
            else:
                st.warning("Please enter an answer before submitting.")

# Results section
if st.session_state.evaluated:
    st.divider()
    st.markdown("### 📊 Results")
    
    res = st.session_state.evaluation_result
    
    if res['is_correct']:
        st.success(f"✅ **Correct!** {res['feedback']}")
        st.balloons()
    else:
        st.error(f"❌ **Not quite right.** {res['feedback']}")
        with st.expander("🔍 Show Correct Answer", expanded=True):
            st.info(f"**Valid answer:** {st.session_state.correct_example}")
    
    st.markdown("---")
    
    # Action buttons
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔄 Try Another (Same Rule)", use_container_width=True):
            generate_same_rule()
            st.rerun()
    
    with col2:
        if st.button("✅ I've Mastered This (Next Rule)", type="primary", use_container_width=True):
            # Add to blacklist only if they got it correct OR if they manually mark as mastered
            if res['is_correct']:
                st.session_state.blacklist.append(st.session_state.rule_desc)
                st.session_state.history.append({
                    "rule": st.session_state.rule_desc,
                    "correct": True,
                    "timestamp": "just now"
                })
            pick_new_rule()
            st.rerun()
    
    with col3:
        if st.button("📝 Review My Answer", use_container_width=True):
            st.markdown("**Your answer:**")
            st.code(st.session_state.user_answer, language='text')
            st.markdown("**Expected answer:**")
            st.code(st.session_state.correct_example, language='text')

# Sidebar with statistics and info
with st.sidebar:
    st.markdown("## 📊 Your Progress")
    
    # Mastered rules list
    if st.session_state.blacklist:
        st.markdown("### ✅ Mastered Rules")
        for rule in st.session_state.blacklist[-5:]:  # Show last 5
            st.caption(f"• {rule[:60]}...")
        if len(st.session_state.blacklist) > 5:
            st.caption(f"... and {len(st.session_state.blacklist) - 5} more")
    else:
        st.info("No rules mastered yet. Start practicing!")
    
    st.divider()
    
    st.markdown("## 💡 Tips for Success")
    st.markdown("""
    1. **Read the rule carefully** before answering
    2. **Study the examples** to understand the pattern
    3. **Maintain the exact meaning** - don't change what the sentence says
    4. **Check grammar** - your answer must be grammatically correct
    5. **Use the 'Try Another' button** to practice the same rule multiple times
    """)
    
    st.divider()
    
    st.markdown("## 🎯 Categories Overview")
    categories = [cat['category_name'] for cat in data['transformation_categories']]
    for cat in categories:
        st.caption(f"• {cat}")
    
    st.divider()
    
    if st.button("🔄 Reset All Progress", type="secondary"):
        st.session_state.blacklist = []
        st.session_state.history = []
        pick_new_rule()
        st.rerun()

# Footer
st.divider()
st.caption("💡 Powered by Groq AI | Master sentence transformations with personalized feedback!")