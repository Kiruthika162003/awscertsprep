import streamlit as st
import datetime
import boto3
import json
import re
import pandas as pd
import uuid
from io import StringIO

# --- CONFIG ---
st.set_page_config(page_title="CertMaster AI", layout="wide")

# --- CUSTOM STYLES ---
st.markdown("""
    <style>
        .quiz-question {
            margin-top: 20px;
            font-weight: bold;
            font-size: 16px;
        }
        .quiz-option {
            margin-left: 15px;
            margin-bottom: 5px;
        }
        .question-box {
            border: 1px solid #ccc;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 5px;
            background-color: #f9f9f9;
        }
    </style>
""", unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.header("Tell us about yourself")
    name = st.text_input("Your Name")
    email = st.text_input("Your Email Address")

    if not name or not email:
        st.warning("Please enter your name and email to proceed.")
        st.stop()

    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        st.error("Invalid email format. Please check your email address.")
        st.stop()

    st.success(f"Welcome, {name} ({email})")
    st.session_state["user_name"] = name
    st.session_state["user_email"] = email

# --- CERTIFICATION SETUP ---
certification_options = {
    "CLF-C01": "AWS Certified Cloud Practitioner",
    "ACP-ML": "AWS Certified AI Practitioner",
    "MLA-C02": "AWS Certified Machine Learning Engineer - Associate",
    "DEA-C01": "AWS Certified Data Engineer - Associate",
    "DVA-C01": "AWS Certified Developer - Associate",
    "SAA-C03": "AWS Certified Solutions Architect - Associate",
    "SOA-C02": "AWS Certified SysOps Administrator - Associate",
    "DOP-C02": "AWS Certified DevOps Engineer - Professional",
    "SAP-C02": "AWS Certified Solutions Architect - Professional",
    "ANS-C01": "AWS Certified Advanced Networking - Specialty",
    "MLS-C01": "AWS Certified Machine Learning - Specialty",
    "SCS-C01": "AWS Certified Security - Specialty",
}

st.title("CertMaster AI - AWS Certification Planner")

# --- STEP 1: SELECT CERT & DATE ---
st.header("Step 1: Set Your Certification Goal")
col1, col2 = st.columns(2)
with col1:
    cert_code = st.selectbox("Choose AWS Certification", list(certification_options.keys()),
                             format_func=lambda x: certification_options[x], key="cert_select")
    cert_name = certification_options[cert_code]
with col2:
    target_date = st.date_input("When is your exam day?", min_value=datetime.date.today())

if cert_name and target_date:
    st.success(f"Great! You're aiming for **{cert_name}** by **{target_date}**.")

# --- BEDROCK CLIENT (Cached) ---
@st.cache_resource
def get_bedrock_client():
    try:
        # Attempt to create a Bedrock client using credentials from Streamlit secrets
        bedrock = boto3.client(
            "bedrock-runtime",
            region_name="us-east-1",  # Replace with your AWS region
            aws_access_key_id=st.secrets["aws_access_key_id"],
            aws_secret_access_key=st.secrets["aws_secret_access_key"],
        )
        st.info("Using credentials from Streamlit Secrets.")
        return bedrock  # Return the Bedrock client if creation is successful
    except Exception as e:
        st.error(f"Error creating Bedrock client from Streamlit Secrets: {e}")
        # If Streamlit Secrets fail, attempt to create a Bedrock client using IAM role
        try:
            bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
            st.info("Using IAM Role.")
            return bedrock  # Return the Bedrock client if creation is successful
        except Exception as e:
            st.error(f"Error creating Bedrock client from IAM Role: {e}")
            st.stop()  # Stop execution if client creation fails

bedrock = get_bedrock_client()

# --- STEP 2: GENERATE STUDY PLAN ---
st.header("Step 2: AI-Powered Study Plan")

def generate_cert_study_plan(cert_name, days_left):
    prompt = f"""You are an AWS Certified Instructor.

Create a **comprehensive, day-by-day study plan** for the AWS **{cert_name}** exam to be completed in **{days_left} days**.

Strict rules:
- The plan must **cover 100% of the exam guide topics** for this specific certification.
- Include services from **all domains**: Compute, Storage, Networking, Databases, Security, IAM, Monitoring, Costing, etc.
- Follow the **official AWS exam guide** structure with weighted focus based on exam scoring.
- Include **real AWS service names** like Lambda, CloudWatch, VPC, Route 53, IAM, S3, Kinesis, etc.
- Do not generalize or skip edge-case services like AWS Outposts or Snowball if part of the exam.
- Allocate days for **revision, practice quizzes, mock tests**, and **hands-on labs**.
- Format:
Day 1 - Domain: Subtopics and AWS Services
Day 2 - Domain: Subtopics and AWS Services
...
Day N - Final Mock Test, Time Management, Exam Day Tips

Keep it motivating and realistic.
"""
    body = json.dumps({"prompt": prompt})
    try:
        response = bedrock.invoke_model(
            modelId="meta.llama3-70b-instruct-v1:0",
            contentType="application/json",
            accept="application/json",
            body=body.encode("utf-8"),
        )
        result = json.loads(response["body"].read().decode("utf-8"))
        return result.get("generation", result.get("outputText", "No study plan generated."))
    except Exception as e:
        st.error(f"Error generating study plan: {str(e)}")
        return None

today = datetime.date.today()
days_left = (target_date - today).days
if st.button("Generate Study Plan"):
    with st.spinner("Generating study plan..."):
        full_study_plan = generate_cert_study_plan(cert_name, days_left)
        if full_study_plan: # Only update session state if the study plan was generated
            st.session_state["study_plan"] = full_study_plan
if "study_plan" in st.session_state:
    st.subheader("Your Personalized Study Plan")
    if st.session_state["study_plan"]: # Only display if study_plan has data
        st.markdown(st.session_state["study_plan"].replace("\n", "  \n"))
    else:
        st.warning("No study plan available. Please try generating it again.")

# --- STEP 3: QUIZ GENERATION ---
st.header("Step 3: Practice Quiz")
quiz_topic = st.text_input("Enter a topic for the quiz:")
if quiz_topic:
    if st.button("Generate Quiz"):
        def generate_questions_llama(topic, cert):
            prompt = f"""You are a trainer for AWS {cert}.
Generate 5 multiple-choice questions on '{topic}'.
Format:
Q1: Question
A) Option
B) Option
C) Option
Answer: A - Explanation"""
            body = json.dumps({"prompt": prompt})
            try:
                response = bedrock.invoke_model(
                    modelId="meta.llama3-70b-instruct-v1:0",
                    contentType="application/json",
                    accept="application/json",
                    body=body.encode("utf-8"),
                )
                result = json.loads(response["body"].read().decode("utf-8"))
                return result.get("generation", result.get("outputText", "No questions generated."))
            except Exception as e:
                st.error(f"Error generating quiz questions: {str(e)}")
                return None

        raw_quiz = generate_questions_llama(quiz_topic, cert_name)
        if raw_quiz: #only proceed if raw_quiz has values
            pattern = r"Q\d+:.*?(?=Q\d+:|$)"
            questions = re.findall(pattern, raw_quiz, re.DOTALL)
            st.session_state["quiz_questions"] = questions
        else:
            st.warning("Failed to generate quiz. Please try again.")


# --- TAKE THE QUIZ ---
if "quiz_questions" in st.session_state:
    st.subheader("Take the Quiz")
    quiz_form = st.form("quiz_form")
    user_answers = {}

    for i, qblock in enumerate(st.session_state["quiz_questions"]):
        match_question = re.search(r"Q\d+: (.*?)\n", qblock)
        if match_question:
            question_text = match_question.group(1)
        else:
            st.warning(f"Could not parse question text for Q{i+1}")
            continue

        options = re.findall(r"([A-C])\) (.*?)(?=\n|$)", qblock)  # Corrected regex
        if not options:
            st.warning(f"Could not parse options for Q{i+1}")
            continue

        quiz_form.markdown("<div class='question-box'>", unsafe_allow_html=True)
        quiz_form.markdown(f"<div class='quiz-question'>Q{i+1}: {question_text}</div>", unsafe_allow_html=True)

        # Create a dictionary to map option letters to their text
        option_dict = {opt[0]: opt[1] for opt in options}

        selected = quiz_form.radio(
            f"Choose your answer for question {i+1}:",
            list(option_dict.keys()),  # Use the option letters as keys
            format_func=lambda x: f"{x}) {option_dict[x]}",  # Format the display
            key=f"q{i}"
        )
        user_answers[i] = selected
        quiz_form.markdown("</div>", unsafe_allow_html=True)

    if quiz_form.form_submit_button("Submit Quiz"):
        correct = 0
        feedback = []
        for i, qblock in enumerate(st.session_state["quiz_questions"]):
            match = re.search(r"Answer:\s*([A-C])\s*-\s*(.*)", qblock)
            if not match:
                feedback.append(f"Q{i+1}: ❓ Answer not provided.")
                continue
            correct_letter = match.group(1)
            correct_text = match.group(2)
            if user_answers.get(i) == correct_letter:
                correct += 1
                feedback.append(f"Q{i+1}: ✅ Correct - {correct_letter} - {correct_text}")
            else:
                feedback.append(f"Q{i+1}: ❌ Incorrect - Your answer: {user_answers.get(i)} | Correct: {correct_letter} - {correct_text}")

        st.subheader("Quiz Results")
        score_pct = (correct / len(st.session_state["quiz_questions"])) * 100
        st.markdown(f"### Your Score: **{correct}/{len(st.session_state['quiz_questions'])}** ({score_pct:.2f}%)")

        if score_pct >= 80:
            st.success("Excellent work! You're well on your way to acing the exam!")
        elif score_pct >= 60:
            st.info("Good effort! Keep reviewing and practicing.")
        else:
            st.warning("Keep studying! Focus on weak areas and try again.")

        with st.expander("Detailed Feedback"):
            for fb in feedback:
                st.markdown(fb)

        del st.session_state["quiz_questions"]

# --- STEP 4: ASK A QUESTION ---
st.header("Step 4: Ask Any Questions")
question_input = st.text_area("Have a doubt or want to ask something?", key="ask_input")
if question_input:
    st.session_state["last_question"] = question_input
    st.success("Thanks! Your question has been saved.")
if "last_question" in st.session_state:
    st.markdown("#### Your Last Question")
    st.info(st.session_state["last_question"])

# --- STEP 5: AI MENTOR ANSWER ---
st.header("Step 5: AI Mentor's Answer")

if st.button("Get AI Answer to My Question"):
    with st.spinner("Generating expert answer..."):
        try:
            prompt = f"""
You are a highly experienced AWS Certification Mentor.
Answer this user's question in a helpful, detailed, and accurate way.

User's Question:
{st.session_state["last_question"]}
"""
            body = json.dumps({"prompt": prompt})
            response = bedrock.invoke_model(
                modelId="meta.llama3-70b-instruct-v1:0",
                contentType="application/json",
                accept="application/json",
                body=body.encode("utf-8"),
            )
            result = json.loads(response["body"].read().decode("utf-8"))
            ai_answer = result.get("generation", result.get("outputText", "No answer generated."))

            # Store the AI answer in session state
            st.session_state["ai_answer"] = ai_answer

            # Save to S3
            s3 = boto3.client("s3",  #added credentials here as well, in case the bedrock client wasn't instantiated with streamlits
            aws_access_key_id=st.secrets["aws_access_key_id"],
            aws_secret_access_key=st.secrets["aws_secret_access_key"],)
            safe_name = re.sub(r"[^a-zA-Z0-9]", "_", st.session_state["user_name"])
            file_key = f"certmaster-answers/{safe_name}/{str(uuid.uuid4())}.txt"
            combined_text = f"Q: {st.session_state['last_question']}\n\nA:\n{ai_answer}"
            s3.put_object(Bucket="subkriti", Key=file_key, Body=combined_text.encode("utf-8"))
            st.info("This conversation has been saved to S3.")
        except Exception as e:
            st.error(f"Error generating answer: {str(e)}")
        finally: #moved display here
            if "ai_answer" in st.session_state:
                st.success("Here’s what your AI mentor says:")
                st.markdown(st.session_state["ai_answer"].replace("\n", "  \n"))
