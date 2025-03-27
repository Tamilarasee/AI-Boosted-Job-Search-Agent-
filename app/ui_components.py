import streamlit as st
import requests
import time


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
    
    # Job preference fields
    target_roles = st.text_input(
        "Target Roles (comma separated)", 
        help="e.g., Machine Learning Engineer, Data Scientist"
    )
    
    primary_skills = st.text_input(
        "Primary Skills (comma separated) ",
        help="e.g., Python, SQL, Machine Learning"
    )
    
    preferred_location = st.text_input(
        "Preferred Locations (comma separated)",
        help="e.g., San Francisco, Remote, New York"
    )
    
    job_type = st.multiselect(
        "Job Type", 
        options=["Full-time", "Part-time", "Contract", "Internship"],
        
    )
    
    additional_preferences = st.text_area(
        "Additional Preferences", 
        help="Any other requirements or preferences"
    )

    # Submit button
    if st.button("Search Jobs"):
        if target_roles and primary_skills:
            with st.spinner("Searching for matching jobs..."):
                try:
                    # convert string to list
                    target_roles = [role.strip() for role in target_roles.split(",")]
                    primary_skills = [skill.strip() for skill in primary_skills.split(",")]

                    response = requests.post(
                        f"{API_URL}/api/search",
                        json={
                            "target_roles": target_roles,
                            "primary_skills": primary_skills,
                            "preferred_location": preferred_location,
                            "job_type": job_type[0] if job_type else "",
                            "additional_preferences": additional_preferences
                        }
                    )
                    
                    if response.status_code == 200:
                        results = response.json()
                        
                        # Display search statistics
                        st.success(f"Found {results['filtered_jobs_count']} matching jobs out of {results['total_jobs_found']} total jobs")
                        
                        # Sort jobs by date_posted
                        jobs = sorted(results['jobs'], 
                                   key=lambda x: x['date_posted'],
                                   reverse=True)  # Most recent first
                        
                        # Display each job
                        for job in jobs:
                            with st.expander(f"{job['title']} at {job['company']} - {job['location']}"):
                                st.write(f"**Posted:** {job['date_posted']}")
                                st.write(f"**Company:** {job['company']}")
                                st.write(f"**Location:** {job['location']}")
                                st.write(f"**Skills Matched:** {len(job['job_matched_skills'])} skills")
                                
                                # Display matched skills
                                st.write("**Matched Skills:**")
                                for skill, terms in job['job_matched_skills'].items():
                                    st.write(f"- {skill}: {', '.join(terms)}")
                                
                                st.write("**Job Description:**")
                                st.write(job['description'])
                                
                                # Apply button
                                if st.button(f"Apply to {job['company']}", key=job['apply_url']):
                                    st.markdown(f"[Apply Here]({job['apply_url']})")
                    else:
                        st.error("Failed to fetch job results. Please try again.")
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")
        else:
            st.error("Please enter at least one target role and primary skill.")
