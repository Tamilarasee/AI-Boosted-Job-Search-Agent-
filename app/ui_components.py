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
                    st.session_state.auth_token = data.get("user", {}).get("access_token")
                    st.session_state.current_page = "user_details"
                    st.rerun()
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

def user_details_form():
    st.subheader("User Details")
    full_name = st.text_input("Full Name")
    
    uploaded_resumes = st.file_uploader(
        "Upload your Resumes (PDF)",
        type = ["pdf"],
        accept_multiple_files= True)

    submit_button = st.button("Next")

    if submit_button:
        if full_name and uploaded_resumes:
            with st.spinner("Processing resumes..."):
                try:
                    name = {"name": full_name}
                    pdf_files = [
                        ("resumes", (resume.name, resume.getvalue(), resume.type))
                        for resume in uploaded_resumes
                    ]
                    
                    # Include auth token if available
                    if "auth_token" in st.session_state:
                        name["token"] = st.session_state.auth_token
                    
                    response = requests.post(
                        f"{API_URL}/users/details",                            
                        data=name,
                        files=pdf_files                            
                    )
                    if response.status_code == 200:
                        st.success("Details submitted successfully!")
                        # Store user ID in session state from the response
                        response_data = response.json()
                        if 'user_id' not in st.session_state:   
                            st.session_state.user_id = response_data["user_id"]
                        st.session_state.current_page = "job_preferences"
                        st.rerun()
                    else:
                        st.error("Failed to save user details. Please try again.")
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")
        else:
            st.error("Please fill the Name and upload your Resumes.")



def job_preferences_form():
    st.subheader("Job Search Preferences")
    
    # Get user name if available
    user_name = st.session_state.get("full_name", "")
    if user_name:
        st.write(f"Hello, {user_name}! Let's find the perfect job for you.")
    
    # --- Use 3 columns in wide mode ---
    col1, col2, col3 = st.columns(3) 

    with col1:
        target_roles = st.text_input(
            "Target Roles (comma separated)",
            help="e.g., Machine Learning Engineer, Data Scientist"
        )
        primary_skills = st.text_input(
            "Primary Skills (comma separated)",
            help="e.g., Python, SQL, Machine Learning"
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
    col_btn1, col_btn2 = st.columns([1, 3]) # Give Search button more space

    with col_btn1:
        # --- NEW: Insights Button ---
        if st.button("📈 View Career Insights", use_container_width=True):
             st.session_state.current_page = "career_insights"
             st.rerun() # Rerun to change the page displayed by app.py

    with col_btn2:
        # Submit button (original Search Jobs button)
        if st.button("🔍 Search Jobs", type="primary", use_container_width=True):
            if target_roles and primary_skills:
                with st.spinner("Searching for matching jobs..."):
                    try:
                        # convert string to list
                        target_roles_list = [role.strip() for role in target_roles.split(",")]
                        primary_skills_list = [skill.strip() for skill in primary_skills.split(",")]
                        
                        # Print debug info
                        st.write(f"Debug - Sending job_type: {job_type[0] if job_type else 'Full-time'}")
                        
                        # Create the request payload
                        payload = {
                            "user_id": st.session_state.user_id,
                            "target_roles": target_roles_list,
                            "primary_skills": primary_skills_list,
                            "preferred_location": preferred_location,
                            "job_type": job_type[0] if job_type else "Full-time",
                            "additional_preferences": additional_preferences
                        }
                        
                        # Display the full request for debugging
                        st.json(payload)
                        
                        response = requests.post(
                            f"{API_URL}/api/search",
                            json=payload
                        )
                        
                        # Display raw response for debugging
                        st.write(f"Response status: {response.status_code}")
                        
                        if response.status_code == 200:
                            results_data = response.json()
                            
                            # --- NEW: Display Overall Skill Gaps ---
                            overall_gaps = results_data.get("overall_skill_gaps", [])
                            if overall_gaps:
                                st.subheader("🎯 Top Focus Areas for You")
                                st.markdown("Based on the jobs analyzed, here are the key skill areas to prioritize:")
                                for item in overall_gaps:
                                    skill = item.get('skill', 'N/A')
                                    estimate = item.get('learn_time_estimate', 'N/A')
                                    st.write(f"- **{skill}:** _{estimate}_")
                                st.divider() # Separate overall summary from individual jobs
                            # --- End Overall Skill Gaps ---

                            # Display search statistics
                            st.success(f"Found {results_data.get('filtered_jobs_count', 0)} matching jobs out of {results_data.get('total_jobs_found', 0)} total jobs analyzed")

                            # Get individual jobs list
                            jobs = results_data.get('jobs', [])
                            
                            # Sort jobs by date_posted if available
                            if jobs:
                                jobs = sorted(jobs, 
                                           key=lambda x: x.get('date_posted', ''),
                                           reverse=True)  # Most recent first
                            
                            # Display each job
                            for job in jobs:
                                # Use container with border for visual separation
                                with st.container(border=True):
                                    col1, col2 = st.columns([3, 1]) # Reintroduce columns

                                    with col1:
                                        st.subheader(f"{job.get('title', 'N/A')}")
                                        st.write(f"🏢 {job.get('company', 'N/A')} | 📍 {job.get('location', 'N/A')}")
                                        st.write(f"**Type:** {job.get('job_type', 'N/A')} | **Posted:** {job.get('date_posted', 'N/A')}")
                                        # Use link_button for Apply Now
                                        if job.get('url'):
                                            st.link_button("Apply Now 🔗", job['url'], type="secondary")

                                    with col2:
                                         # Display Resume Match Score if available
                                         if 'match_percentage' in job:
                                             st.metric(
                                                 "Resume Match",
                                                 f"{job.get('match_percentage', 0):.1f}%",
                                                 delta=None,
                                                 help="Based on semantic similarity between your profile and the job description."
                                             )
                                         else:
                                             st.caption("Match N/A") # Placeholder if no score

                                    # --- AI Analysis Section (now outside columns) ---
                                    analysis = job.get('analysis', {})
                                    # Only show expander if analysis dict exists AND has content
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
                                                    for item in highlights:
                                                        st.write(f"  - {item}")
                                                if removals:
                                                     st.markdown("*Consider Removing/De-emphasizing:*")
                                                     for item in removals:
                                                         st.write(f"  - {item}")
                                            # Removed the redundant 'No specific tips' message here

                                            # This case should now be covered by the outer 'if analysis and (...)' check
                                            # if not missing_skills and not highlights and not removals:
                                            #      st.write("_No specific skill gaps or resume tips were generated._")

                                    else:
                                         # If 'analysis' dict is empty or missing meaningful content
                                         st.caption("_AI analysis not available or no specific insights generated for this job._")
                                    # --- End AI Analysis Section ---

                        else:
                            st.error(f"Failed to fetch job results. Status code: {response.status_code}")
                            try:
                                st.error(f"Error details: {response.json()}")
                            except:
                                st.error(f"Raw response: {response.text}")
                    except Exception as e:
                        st.error(f"An error occurred: {str(e)}")
            else:
                st.error("Please enter at least one target role and primary skill.")

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
