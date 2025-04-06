import streamlit as st
import requests
import uuid



API_URL = "http://localhost:8000"

# Function for the login form
def login_form():
    st.subheader("User Login")
    with st.form(key='login_form'):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submit_button = st.form_submit_button("Login")

        if submit_button:
            try:
                response = requests.post(
                    f"{API_URL}/auth/login",
                    json={"email": email, "password": password}
                )
                if response.status_code == 200:
                    data = response.json()
                    user_info = data.get("user") # Get the user object
                    if user_info:
                        st.session_state.auth_token = user_info.get("access_token") # Or however token is nested
                        st.session_state.user_id = user_info.get("id") # Extract the user ID
                        st.session_state.current_page = "job_preferences"
                        # Ensure user_id was actually set before rerunning
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

    if st.button("Sign Up"):
        st.session_state.current_page = "register"

# Function for the registration form
def registration_form():
    st.subheader("Create a New Account")
    new_email = st.text_input("Email")
    new_password = st.text_input("New Password", type="password")
    confirm_password = st.text_input("Confirm Password", type="password")
    register_button = st.button("Sign Up")

    if register_button:
        if new_password == confirm_password:
            # Register user with Supabase using email
            try:
                response = requests.post(
                    f"{API_URL}/auth/register",
                    json={"email": new_email, "password": new_password}
                )
                if response.status_code == 200:
                    st.success(f"Account created for: {new_email}")
                    st.success("You can now log in with your new account!")
                    st.session_state.current_page = "login"
                    st.rerun()
                else:
                    st.error("Registration failed. Please try again.")
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
        else:
            st.error("Passwords do not match. Please try again.")

    # Button to go back to login
    if st.button("Login"):
        st.session_state.current_page = "login"

# def user_details_form():
#     st.subheader("User Details")
#     full_name = st.text_input("Full Name")
    
#     uploaded_resumes = st.file_uploader(
#         "Upload your Resumes (PDF)",
#         type = ["pdf"],
#         accept_multiple_files= True)

#     submit_button = st.button("Next")

#     if submit_button:
#         if full_name and uploaded_resumes:
#             with st.spinner("Processing resumes..."):
#                 try:
#                     name = {"name": full_name}
#                     pdf_files = [
#                         ("resumes", (resume.name, resume.getvalue(), resume.type))
#                         for resume in uploaded_resumes
#                     ]
                    
#                     # Include auth token if available
#                     if "auth_token" in st.session_state:
#                         name["token"] = st.session_state.auth_token
                    
#                     response = requests.post(
#                         f"{API_URL}/users/details",                            
#                         data=name,
#                         files=pdf_files                            
#                     )
#                     if response.status_code == 200:
#                         st.success("Details submitted successfully!")
#                         # Store user ID in session state from the response
#                         response_data = response.json()
#                         if 'user_id' not in st.session_state:   
#                             st.session_state.user_id = response_data["user_id"]
#                         st.session_state.current_page = "job_preferences"
#                         st.rerun()
#                     else:
#                         st.error("Failed to save user details. Please try again.")
#                 except Exception as e:
#                     st.error(f"An error occurred: {str(e)}")
#         else:
#             st.error("Please fill the Name and upload your Resumes.")



def job_preferences_form():
    st.subheader("Job Search Preferences & Profile")

    # Check for user_id early
    if 'user_id' not in st.session_state:
        st.warning("Please log in to manage preferences and search for jobs.")
        # Optionally add a button to go to login
        return # Don't show the rest of the form if not logged in

    user_id = st.session_state.user_id

    # --- Resume Upload Section ---
    st.markdown("---") # Divider
    st.markdown("**Update Your Resume**")
    st.caption("Upload your latest resume (PDF). We'll analyze it to suggest relevant titles and skills.")

    uploaded_resumes = st.file_uploader(
        "Upload Resumes (PDF)",
        type=["pdf"],
        accept_multiple_files=True, # Allow multiple, though backend might combine them
        key="resume_uploader" # Add a key for state management
    )

    if st.button("🚀 Upload & Analyze Resume"):
        if uploaded_resumes:
            with st.spinner("Processing and analyzing resume(s)... Please wait."):
                try:
                    # Prepare files for requests post
                    files_for_upload = [
                        ("resumes", (resume.name, resume.getvalue(), resume.type))
                        for resume in uploaded_resumes
                    ]
                    # Prepare form data
                    data_payload = {"user_id": user_id}

                    response = requests.post(
                        f"{API_URL}/api/users/upload-analyze-resume",
                        files=files_for_upload,
                        data=data_payload
                    )

                    if response.status_code == 200:
                        st.success("✅ Resume uploaded and analyzed successfully!")
                        response_data = response.json()
                        # Store suggestions in session state
                        st.session_state.suggested_titles = response_data.get("suggested_titles", [])
                        st.session_state.extracted_skills = response_data.get("extracted_skills", [])
                        st.info(f"Suggested Titles: {', '.join(st.session_state.suggested_titles)}")
                        st.info(f"Extracted Skills: {', '.join(st.session_state.extracted_skills)}")
                        st.rerun() # Rerun will clear the uploader implicitly
                    else:
                        try:
                             error_detail = response.json().get("detail", "Unknown upload error")
                        except:
                             error_detail = response.text
                        st.error(f"⚠️ Failed to upload/analyze resume: {error_detail} (Status: {response.status_code})")

                except requests.exceptions.RequestException as req_err:
                    st.error(f"⚠️ Network error connecting to API: {req_err}")
                except Exception as e:
                    st.error(f"⚠️ An unexpected error occurred: {str(e)}")
        else:
            st.warning("Please select at least one PDF resume file to upload.")

    st.markdown("---") # Divider

    # --- Job Preferences Form Inputs ---
    st.markdown("**Define Your Job Search Criteria**")
    st.caption("We'll use relevant titles and skills from your latest uploaded resume. Feel free to add specific roles or skills below to refine the search further.")

    # Get suggestions from session state just for the combination logic later
    suggested_titles_list = st.session_state.get("suggested_titles", [])
    extracted_skills_list = st.session_state.get("extracted_skills", [])

    # Use 3 columns in wide mode
    col1, col2, col3 = st.columns(3)

    with col1:
        # REMOVED pre-filling with 'value=' argument
        target_roles = st.text_input(
            "Target Roles (Optional, comma separated)",
            # REMOVED: value=suggested_titles_str,
            # Updated help text
            help="Add specific roles if you have particular targets in mind."
        )
        primary_skills = st.text_input(
            "Primary Skills (Optional, comma separated)",
            # REMOVED: value=extracted_skills_str,
            # Updated help text
            help="Add specific skills you want to emphasize."
        )

    with col2:
        preferred_location = st.text_input(
            "Preferred Locations (comma separated)",
            help="e.g., San Francisco, Remote, New York"
        )
        job_type = st.multiselect(
            "Job Type",
            options=["Full-time", "Part-time", "Contract", "Internship"],
            default=["Full-time"]
        )

    with col3:
        additional_preferences = st.text_area(
            "Additional Preferences",
             height=150, # Adjust as needed
            help="Any other requirements or preferences (e.g., specific industries, company size)"
        )

    # --- End columns ---

    # --- Buttons ---
    col_btn1, col_btn2 = st.columns([1, 3]) # Example layout

    with col_btn1:
        if st.button("📈 View Career Insights", use_container_width=True):
             st.session_state.current_page = "career_insights"
             st.rerun()

    with col_btn2:
        # Submit button (original Search Jobs button)
        if st.button("🔍 Search Jobs", type="primary", use_container_width=True):
            # Get current user input from the widgets
            current_target_roles_str = target_roles
            current_primary_skills_str = primary_skills

            # Get extracted lists from session state
            suggested_titles_list = st.session_state.get("suggested_titles", [])
            extracted_skills_list = st.session_state.get("extracted_skills", [])

            # --- Revised Combination Logic ---

            # 1. Target Roles: Use user input ONLY if provided, otherwise use extracted.
            user_roles_list = [role.strip() for role in current_target_roles_str.split(",") if role.strip()]
            if user_roles_list:
                final_roles_list = user_roles_list
                st.info("Using user-provided target roles.") # Optional feedback
            else:
                final_roles_list = suggested_titles_list
                if final_roles_list:
                     st.info("Using target roles extracted from resume.") # Optional feedback


            # 2. Primary Skills: Combine user input WITH extracted skills, then de-duplicate.
            final_skills_set = set(extracted_skills_list) # Start with extracted
            user_skills_list = {skill.strip() for skill in current_primary_skills_str.split(",") if skill.strip()}
            final_skills_set.update(user_skills_list) # Add user input (duplicates handled by set)
            final_skills_list = list(final_skills_set) # Convert back to list

            # --- End Revised Combination Logic ---


            # Proceed only if we have *some* final roles and skills
            if final_roles_list or final_skills_list:
                 if not final_roles_list:
                      st.warning("No target roles found from resume or input. Search might be broad.")
                 if not final_skills_list:
                      st.warning("No primary skills found from resume or input. Search might be broad.")

                 with st.spinner("Searching for matching jobs..."):
                    try:
                        # Ensure job_type is handled correctly
                        selected_job_type = job_type[0] if job_type else "Full-time"

                        # Use the final combined lists in the payload
                        payload = {
                            "user_id": user_id,
                            "target_roles": final_roles_list,
                            "primary_skills": final_skills_list,
                            "preferred_location": preferred_location,
                            "job_type": selected_job_type,
                            "additional_preferences": additional_preferences
                        }

                        st.write("Debug: Search Payload (Revised Combination)") # Debugging
                        st.json(payload) # Debugging

                        response = requests.post(
                            f"{API_URL}/api/search",
                            json=payload
                        )

                        st.write(f"Response status: {response.status_code}") # Debugging

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

                                    analysis = job.get('analysis', {})
                                    if analysis and (analysis.get('missing_skills') or analysis.get('resume_suggestions', {}).get('highlight') or analysis.get('resume_suggestions', {}).get('consider_removing')):
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
                                                    for item in highlights: st.write(f"  - {item}")
                                                if removals:
                                                     st.markdown("*Consider Removing/De-emphasizing:*")
                                                     for item in removals: st.write(f"  - {item}")
                                    else:
                                         st.caption("_AI analysis not available or no specific insights generated for this job._")
                        else:
                            st.error(f"Failed to fetch job results. Status code: {response.status_code}")
                            try: st.error(f"Error details: {response.json()}")
                            except: st.error(f"Raw response: {response.text}")
                    except Exception as e:
                        st.error(f"An error occurred during job search: {str(e)}")
            else:
                # Updated error message if both resume AND user input yield nothing
                st.error("Could not determine target roles or primary skills. Please upload a resume or enter criteria manually.")

# --- NEW: Career Insights Page Function ---
def career_insights_page():
    st.subheader("🚀 Career Insights Dashboard")
    st.markdown("Analyzing your recent job searches to identify key skill areas for development.")

    if 'user_id' not in st.session_state:
        st.warning("Please log in and complete your profile to view insights.")
        if st.button("Go to Login"):
            st.session_state.current_page = "login"
            st.rerun()
        return

    user_id = st.session_state.user_id

    # --- Call Backend Endpoint ---
    api_endpoint = f"{API_URL}/api/insights/recent-skill-gaps/{user_id}"
    
    try:
        with st.spinner("Analyzing your recent activity..."):
            response = requests.get(api_endpoint, timeout=60) # Increased timeout for LLM call

        if response.status_code == 200:
            data = response.json()
            top_gaps = data.get("top_overall_gaps", [])

            if top_gaps:
                st.markdown("#### Top 5 Skill Focus Areas (Based on Last 7 Days):")
                
                # Display using columns for better layout potentially
                # Or just simple list for now
                for i, gap in enumerate(top_gaps):
                    skill = gap.get('skill', 'N/A')
                    reason = gap.get('reason', 'N/A')
                    with st.container(border=True):
                         st.markdown(f"**{i+1}. {skill}**")
                         st.caption(f"_{reason}_")
                         # Optionally add links or resources here later
                
                st.info("💡 Consider focusing on projects or certifications in these areas to align better with your target roles.", icon="ℹ️")

            else:
                st.info("✅ No significant recurring skill gaps identified based on your recent searches, or analysis is pending. Keep exploring!", icon="✅")

        elif response.status_code == 404 and "No recent search history found" in response.text:
             st.info("You haven't searched for jobs recently. Perform some searches to generate insights!", icon="ℹ️")
        else:
            try:
                error_detail = response.json().get("detail", "Unknown error")
            except:
                error_detail = response.text
            st.error(f"Failed to load insights ({response.status_code}): {error_detail}")

    except requests.exceptions.RequestException as e:
        st.error(f"Error connecting to the insights API: {str(e)}")
    except Exception as e:
         st.error(f"An unexpected error occurred while fetching insights: {str(e)}")


    # --- Navigation Back ---
    st.divider()
    if st.button("⬅️ Back to Job Preferences"):
        st.session_state.current_page = "job_preferences"
        st.rerun()
