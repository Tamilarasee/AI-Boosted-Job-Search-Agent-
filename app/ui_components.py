import streamlit as st
import requests
import uuid
import time
import io
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Instantiate the client at the module level
# This will automatically use the OPENAI_API_KEY environment variable
client = OpenAI()

API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000")

# --- NEW: Helper Function for OpenAI Translation ---
def translate_audio_bytes_to_english(audio_bytes: bytes) -> tuple[str | None, str | None]:
    """
    Sends audio bytes to OpenAI Whisper for translation to English using the pre-configured client.

    Args:
        audio_bytes: The WAV audio data as bytes.

    Returns:
        A tuple: (translated_text, error_message).
        One of them will be None.
    """
    print("Attempting translation via OpenAI...")
    try:
        # Prepare file-like object for Whisper API
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "input.wav"

        print("Sending audio to OpenAI Whisper...")
        translation = client.audio.translations.create(
           model="whisper-1",
           file=audio_file,
        )

        if translation.text:
             print("Translation successful.")
             print("\n--- Translated Text (Console Log) ---")
             print(translation.text)
             print("-------------------------------------\n")
             return translation.text, None
        else:
             error_msg = "Translation returned empty text."
             print(f"WARNING: {error_msg}")
             return None, error_msg

    except client.APIError as e:
         error_msg = f"OpenAI API Error: {e}"
         print(f"ERROR: {error_msg}")
         return None, error_msg
    except Exception as e:
        error_msg = f"Unexpected translation error: {e}"
        print(f"ERROR: {error_msg}")
        return None, error_msg
# --- End Helper Function ---

# Function for the login form
def login_form():
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        #st.markdown("<h3 style='text-align: center;'>Login</h3>", unsafe_allow_html=True)
        with st.form(key='login_form'):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")

            form_col1_inner, form_col2_inner, form_col3_inner = st.columns([1, 1.5, 1])
            with form_col2_inner:
                 submit_button = st.form_submit_button("Login", use_container_width=True)

            if submit_button:
                try:
                    response = requests.post(
                        f"{API_URL}/auth/login",
                        json={"email": email, "password": password}
                    )
                    if response.status_code == 200:
                        data = response.json()
                        user_info = data.get("user")
                        if user_info:
                            st.session_state.auth_token = user_info.get("access_token")
                            st.session_state.user_id = user_info.get("id")
                            st.session_state.user_email = user_info.get("email")
                            st.session_state.current_page = "resume_management"
                            if st.session_state.user_id:
                                 st.rerun()
                            else:
                                 st.error("Login succeeded but failed to retrieve user ID.")
                        else:
                            st.error("Login response did not contain user information.")
                    else:
                        st.error("Login failed. Please check your credentials.")
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")

        st.write("")
        st.markdown(
            "<div style='text-align: center;'>Don't have an account? <a href='?action=register' target='_self'>Sign Up</a></div>",
            unsafe_allow_html=True
        )

# Function for the registration form
def registration_form():
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("<h3 style='text-align: center;'>Create a New Account</h3>", unsafe_allow_html=True)
        new_email = st.text_input("Email")
        new_password = st.text_input("New Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")

        signup_btn_col1_inner, signup_btn_col2_inner, signup_btn_col3_inner = st.columns([1, 1.5, 1])
        with signup_btn_col2_inner:
             register_button = st.button("Sign Up", use_container_width=True)

        if register_button:
            if new_password == confirm_password:
                try:
                    response = requests.post(
                        f"{API_URL}/auth/register",
                        json={"email": new_email, "password": new_password}
                    )
                    if response.status_code == 200:
                        st.success(f"Account created for: {new_email}")
                        st.success("Redirecting to login...")
                        st.session_state.current_page = "login"
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error("Registration failed. Please try again.")
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")
            else:
                st.error("Passwords do not match. Please try again.")

        st.write("")
        st.markdown(
            "<div style='text-align: center;'>Already have an account? <a href='?action=login' target='_self'>Login</a></div>",
            unsafe_allow_html=True
        )

# --- NEW: Resume Management Page Function ---
def resume_management_page():
    st.markdown("<h2 style='text-align: center;'>📄 Resume</h2>", unsafe_allow_html=True)

    if 'user_id' not in st.session_state:
        st.warning("Please log in to manage your resume.")
        # Optionally add button to go to login
        return

    user_id = st.session_state.user_id

    # --- Resume Upload Section ---
    st.markdown("**Upload or Update Your Resume**")
    st.caption("Upload your latest resume (PDF). We'll analyze it to suggest relevant job titles and skills for your profile.")

    # Display success message after rerun if applicable
    if st.session_state.get('resume_upload_success', False): # Use .get for safety
        st.success("✅ Resume uploaded and analyzed successfully!")
        st.session_state.resume_upload_success = False # Reset the flag

    uploaded_resumes = st.file_uploader(
        "Upload Resumes (PDF)", type=["pdf"], accept_multiple_files=True, key="resume_uploader_page" # Unique key
    )

    if st.button("🚀 Upload & Analyze Resume"):
        if uploaded_resumes:
            with st.spinner("Processing and analyzing resume(s)... Please wait."):
                try:
                    files_for_upload = [("resumes", (r.name, r.getvalue(), r.type)) for r in uploaded_resumes]
                    data_payload = {"user_id": user_id}
                    response = requests.post(f"{API_URL}/api/users/upload-analyze-resume", files=files_for_upload, data=data_payload)

                    if response.status_code == 200:
                        st.session_state.resume_upload_success = True # Set flag for display after rerun
                        response_data = response.json()
                        # Store suggestions in session state (used by job_preferences_form)
                        st.session_state.suggested_titles = response_data.get("suggested_titles", [])
                        st.session_state.extracted_skills = response_data.get("extracted_skills", [])
                        # Provide feedback here as well
                        st.info(f"Suggested Titles: {', '.join(st.session_state.suggested_titles)}")
                        st.info(f"Extracted Skills: {', '.join(st.session_state.extracted_skills)}")
                        st.rerun() # Rerun to show success message and clear uploader
                    else:
                        error_detail = response.json().get("detail", response.text)
                        st.error(f"⚠️ Failed to upload/analyze resume: {error_detail} (Status: {response.status_code})")
                except requests.exceptions.RequestException as req_err:
                    st.error(f"⚠️ Network error: {req_err}")
                except Exception as e:
                    st.error(f"⚠️ Unexpected error: {str(e)}")
        else:
            st.warning("Please select at least one PDF resume file.")

    # Display current suggested titles/skills if they exist
    st.divider()
    st.markdown("**Current Profile Suggestions**")
    if st.session_state.get("suggested_titles") or st.session_state.get("extracted_skills"):
         st.info(f"Suggested Titles: {', '.join(st.session_state.get('suggested_titles', []))}")
         st.info(f"Extracted Skills: {', '.join(st.session_state.get('extracted_skills', []))}")
    else:
         st.caption("No suggestions yet. Upload a resume to generate them.")


# --- End Resume Management Page Function ---

def job_preferences_form():
    st.markdown("<h2 style='text-align: center;'>🔍 Job Preferences </h2>", unsafe_allow_html=True)

    if 'user_id' not in st.session_state:
        st.warning("Please log in to manage preferences and search for jobs.")
        return

    user_id = st.session_state.user_id

    # --- Initialize State Variables ---
    if 'pref_text_area_value' not in st.session_state: st.session_state.pref_text_area_value = ""
    if 'just_processed_audio' not in st.session_state: st.session_state.just_processed_audio = False

    st.markdown("---")
    st.markdown("**Define Your Job Search Criteria**")
    st.caption("Suggestions are based on your latest analyzed resume. Add specific roles or skills below to refine.")

    suggested_titles_list = st.session_state.get("suggested_titles", [])
    extracted_skills_list = st.session_state.get("extracted_skills", [])

    col1, col2, col3 = st.columns(3)

    with col1:
        target_roles = st.text_input("Target Roles (Optional, comma separated)", help="Specific roles?")
        primary_skills = st.text_input("Primary Skills (Optional, comma separated)", help="Specific skills?")

    with col2:
        preferred_location = st.text_input("Preferred Locations (comma separated)", help="e.g., San Francisco, Remote")
        job_type = st.multiselect("Job Type", options=["Full-time", "Part-time", "Contract", "Internship"], default=["Full-time"])

    with col3:
        # --- Additional Preferences Text Area ONLY ---
        st.session_state.pref_text_area_value = st.text_area(
            "Additional Preferences",
            value=st.session_state.pref_text_area_value,
            height=110, # Keep height adjustment
            key="pref_text_area_widget",
            help="Type any other requirements (industry, company size, etc.). You can also use voice input below (supports 58 languages)." # Adjusted help
        )

    # --- End columns for inputs ---
    st.markdown("---")

    # --- Voice Input and Search Button Side-by-Side (Equal Columns) ---
    voice_col, search_col = st.columns(2) # Use 2 equal columns

    with voice_col: # Microphone now in the first column
        # This is the SINGLE microphone input now
        audio_data = st.audio_input(
            label=" ", # Keep label collapsed
            label_visibility="collapsed",
            key="audio_input_widget_side", # Ensure this key is unique if needed
            help="Click the mic to record preferences (translates 58 languages to English). Click again to stop."
        )

    with search_col: # Search button now in the second column
        # --- Add vertical space ABOVE the button ---
        # Adjust the number of <br> or use margin-top in px for finer control
        st.markdown("<div style='margin-top: 5px;'></div>", unsafe_allow_html=True) # Reduced space
        # OR use margin-top: st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)

        # Render the button
        search_button_clicked = st.button("🔍 Search Jobs", use_container_width=True)


    # --- Process Audio Data (Logic remains the same, location unchanged) ---
    if audio_data is not None:
        # Check if this is NEW audio data we haven't processed yet
        # Use .get with a default for safety when checking the flag
        if not st.session_state.get('just_processed_audio', False):
            wav_bytes = audio_data.getvalue()
            print(f"Received NEW {len(wav_bytes)} bytes from st.audio_input (Processing).")
            if wav_bytes:
                with st.spinner("Translating your recording..."):
                    translated_text, error_message = translate_audio_bytes_to_english(wav_bytes)
                if translated_text:
                    st.success("✅ Voice input translated and added to 'Additional Preferences'.")
                    # Use .get with default for safety when reading text area value
                    current_text = st.session_state.get('pref_text_area_value', "")
                    separator = " " if current_text else ""
                    # Update the state variable that the text_area widget uses
                    st.session_state.pref_text_area_value = current_text + separator + translated_text
                    # Set flag indicating we just processed audio data associated with the current widget state
                    st.session_state.just_processed_audio = True
                    st.rerun() # Rerun to update the text area display IMMEDIATELY
                else:
                    st.error(f"⚠️ Translation failed: {error_message}")
                    # Optional: Reset flag on failure if needed, but maybe not
                    # st.session_state.just_processed_audio = False
            else:
                st.warning("Audio input received but contained no data.")
                # Optional: Reset flag on empty data if needed
                # st.session_state.just_processed_audio = False
        else:
            # This 'audio_data' is not None, but the 'just_processed_audio' flag is True.
            # This means it's the same audio data present in the widget after the post-translation rerun.
            # We should ignore it and NOT reset the flag here. The flag signifies that the
            # current non-None audio_data in the widget corresponds to what's already processed.
            print("Ignoring stale audio data present in widget after rerun.")
            pass # Explicitly do nothing with the audio or the flag

    elif audio_data is None:
        # Audio widget is empty (cleared by user or never used).
        # If the flag was previously True, it means the user just cleared the input
        # that we had processed, so we should reset the flag.
        if st.session_state.get('just_processed_audio', False):
             print("Audio input cleared, resetting processed flag.")
             st.session_state.just_processed_audio = False # Reset the flag
    # --- End Audio Processing ---


    # --- Search Logic (Triggered by the stored button state) ---
    if search_button_clicked:
            # Get current user input from the widgets
            current_target_roles_str = target_roles
            current_primary_skills_str = primary_skills
            current_additional_prefs = st.session_state.pref_text_area_value # Use state value

            user_roles_list = [r.strip() for r in current_target_roles_str.split(",") if r.strip()]
            final_roles_list = user_roles_list if user_roles_list else suggested_titles_list
            if user_roles_list: st.info("Using user-provided target roles.")
            elif final_roles_list: st.info("Using target roles extracted from resume.")

            final_skills_set = set(extracted_skills_list)
            user_skills_list = {s.strip() for s in current_primary_skills_str.split(",") if s.strip()}
            final_skills_set.update(user_skills_list)
            final_skills_list = list(final_skills_set)

            if final_roles_list or final_skills_list:
                 if not final_roles_list: st.warning("No target roles found. Search might be broad.")
                 if not final_skills_list: st.warning("No primary skills found. Search might be broad.")

                 with st.spinner("Searching for matching jobs..."):
                    try:
                        selected_job_type = job_type[0] if job_type else "Full-time"
                        payload = {
                            "user_id": user_id,
                            "target_roles": final_roles_list,
                            "primary_skills": final_skills_list,
                            "preferred_location": preferred_location,
                            "job_type": selected_job_type,
                            "additional_preferences": current_additional_prefs
                        }

                        response = requests.post(f"{API_URL}/api/search", json=payload)

                        if response.status_code == 200:
                            results_data = response.json()
                            overall_gaps = results_data.get("overall_skill_gaps", [])
                            if overall_gaps:
                                st.subheader("🎯 Top Focus Areas for You")
                                st.markdown("Based on the jobs analyzed, here are the key skill areas to prioritize:")
                                for item in overall_gaps:
                                    skill = item.get('skill', 'N/A')
                                    estimate = item.get('learn_time_estimate', 'N/A')
                                    st.write(f"- **{skill}:** _{estimate}_")
                                st.divider()

                            st.success(f"Found {results_data.get('filtered_jobs_count', 0)} matching jobs out of {results_data.get('total_jobs_found', 0)} total jobs analyzed")

                            jobs = results_data.get('jobs', [])
                            if jobs:
                                jobs = sorted(jobs, key=lambda x: x.get('date_posted', ''), reverse=True)

                            for job in jobs:
                                with st.container(border=True):
                                    col1_job, col2_job = st.columns([3, 1])
                                    with col1_job:
                                        st.subheader(f"{job.get('title', 'N/A')}")
                                        st.write(f"🏢 {job.get('company', 'N/A')} | 📍 {job.get('location', 'N/A')}")
                                        st.write(f"**Type:** {job.get('job_type', 'N/A')} | **Posted:** {job.get('date_posted', 'N/A')}")
                                        if job.get('url'):
                                            st.link_button("Apply Now 🔗", job['url'], type="secondary")
                                    with col2_job:
                                        if 'match_percentage' in job:
                                             st.metric("Resume Match", f"{job.get('match_percentage', 0):.1f}%")
                                        else:
                                             st.caption("Match N/A")

                                    # --- Moved Expander Here ---
                                    analysis = job.get('analysis', {})
                                    if analysis and any(k in analysis for k in ['missing_skills', 'resume_suggestions']):
                                        with st.expander("🔍 Show AI Analysis & Tips", expanded=False):
                                            missing_skills = analysis.get('missing_skills', [])
                                            if missing_skills:
                                                st.markdown("**Missing Skills & Learning Time:**")
                                                for item in missing_skills:
                                                    skill = item.get('skill', 'N/A')
                                                    estimate = item.get('learn_time_estimate', 'N/A')
                                                    st.write(f"- **{skill}:** _{estimate}_")

                                            suggestions = analysis.get('resume_suggestions', {})
                                            highlights = suggestions.get('highlight', [])
                                            removals = suggestions.get('consider_removing', [])

                                            if highlights or removals:
                                                st.markdown("**Resume Tailoring Suggestions:**")
                                                if highlights:
                                                    st.markdown("*Consider Highlighting:*")
                                                    for item in highlights:
                                                        st.write(f"  - {item}")
                                                if removals:
                                                     st.markdown("*Consider Removing/De-emphasizing:*")
                                                     for item in removals:
                                                         st.write(f"  - {item}")
                                    else:
                                        # This ensures consistent structure even if analysis is empty/not shown
                                         st.caption("_AI analysis not available or no specific insights generated._")
                                    # --- End Moved Expander ---
                        else:
                            st.error(f"Failed to fetch job results ({response.status_code}): {response.text}")
                    except Exception as e:
                        st.error(f"An error occurred during job search: {str(e)}")
            else:
                st.error("Could not determine target roles or skills. Please upload a resume or enter criteria.")

    # --- End Action Buttons ---

def career_insights_page():
    st.markdown("<h2 style='text-align: center;'>📈 Career Insights Dashboard</h2>", unsafe_allow_html=True)
    st.markdown("Analyzing your recent job searches to identify key skill areas for development.")

    if 'user_id' not in st.session_state:
        st.warning("Please log in and complete your profile to view insights.")
        if st.button("Go to Login"):
            st.session_state.current_page = "login"
            st.rerun()
        return

    user_id = st.session_state.user_id
    api_endpoint = f"{API_URL}/api/insights/recent-skill-gaps/{user_id}"

    try:
        with st.spinner("🧠 Analyzing your recent activity..."):
            response = requests.get(api_endpoint, timeout=90)

        if response.status_code == 200:
            data = response.json()
            top_gaps = data.get("top_overall_gaps", [])
            if top_gaps:
                st.markdown("#### Top Skill Focus Areas (Based on Last 7 Days):")
                for i, gap in enumerate(top_gaps):
                    skill = gap.get('skill', 'N/A')
                    estimate = gap.get('learn_time_estimate', 'N/A')
                    reason = gap.get('reason', 'N/A')
                    with st.container(border=True):
                         col_skill, col_time = st.columns([3, 1])
                         with col_skill: st.markdown(f"**{i+1}. {skill}**")
                         with col_time: st.markdown(f"<div style='text-align: right;'>⏳ Invest: {estimate}</div>", unsafe_allow_html=True)
                         st.write(reason)
                st.info("💡 Consider focusing on projects or certifications in these areas.", icon="ℹ️")
            else:
                st.info("✅ No significant recurring skill gaps identified recently, or analysis is pending.", icon="✅")
        elif response.status_code == 404:
             st.info("Perform some job searches to generate insights!", icon="ℹ️")
        else:
            error_detail = response.json().get("detail", response.text)
            st.error(f"Failed to load insights ({response.status_code}): {error_detail}")
    except requests.exceptions.RequestException as e:
        st.error(f"Error connecting to insights API: {str(e)}")
    except Exception as e:
         st.error(f"An unexpected error occurred fetching insights: {str(e)}")

    st.divider()
    # REMOVE the back button, sidebar handles navigation now
    # if st.button("⬅️ Back to Job Preferences"):
    #     st.session_state.current_page = "job_preferences"
    #     st.rerun()
# --- End career_insights_page ---
