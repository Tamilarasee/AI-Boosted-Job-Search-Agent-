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
    
    location_preference = st.text_input(
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
    if st.button("Save Preferences & Continue to Job Search"):
        if target_roles and primary_skills:
            # Store preferences in session state
            st.session_state.user_preferences = {
                "target_roles": target_roles,
                "primary_skills": primary_skills,
                "location_preference": location_preference,
                "job_type": job_type,
                "additional_preferences": additional_preferences
            }
            
            # Also save to database if needed
            try:
                response = requests.post(
                    f"{API_URL}/users/preferences",
                    json={
                        "user_id": st.session_state.get("user_id", ""),
                        "target_roles": target_roles,
                        "primary_skills": primary_skills,
                        "location_preference": location_preference,
                        "job_type": job_type,
                        "additional_preferences": additional_preferences
                    }
                )
                
                if response.status_code == 200:
                    st.success("Preferences saved successfully!")
                    st.session_state.current_page = "job_search"
                    st.rerun()
                else:
                    # Even if DB save fails, we can still continue with session data
                    st.warning("Could not save preferences to database, but you can still continue.")
                    st.session_state.current_page = "job_search"
                    st.rerun()
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
                # Still allow continuing to search
                st.session_state.current_page = "job_search"
                st.rerun()
        else:
            st.error("Please enter at least one target role and primary skill.")

def job_search_form():
    st.subheader("Job Search")
    
    # Check if user preferences exist in session state
    if "user_preferences" not in st.session_state:
        st.warning("Please set your job preferences first.")
        if st.button("Go to Preferences"):
            st.session_state.current_page = "job_preferences"
            st.rerun()
        return
    
    # Display current preferences
    preferences = st.session_state.user_preferences
    st.write("### Your Job Preferences")
    
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Target Roles:** {preferences.get('target_roles', '')}")
        st.write(f"**Primary Skills:** {preferences.get('primary_skills', '')}")
        st.write(f"**Location:** {preferences.get('location_preference', '')}")
    
    with col2:
        st.write(f"**Job Type:** {', '.join(preferences.get('job_type', []))}")
        if preferences.get('additional_preferences'):
            st.write(f"**Additional Preferences:** {preferences.get('additional_preferences', '')}")
    
    # Option to modify search
    st.write("### Refine Your Search")
    
    # Simplified search options
    search_role = st.text_input(
        "Target Role",
        value=preferences.get('target_roles', '').split(',')[0]
    )
    
    search_location = st.text_input(
        "Location",
        value=preferences.get('location_preference', ''),
        help="Enter city, state, country, or 'Remote'. This filters jobs by location."
    )
    
    search_skills = st.text_input(
        "Skills (comma separated)",
        value=preferences.get('primary_skills', '')
    )
    
    job_types = st.multiselect(
        "Job Type",
        options=["Full-time", "Part-time", "Contract", "Internship"],
        default=preferences.get('job_type', ["Full-time"])
    )
    
    # Initialize session state variables if they don't exist
    if "search_id" not in st.session_state:
        st.session_state.search_id = None
    
    if "job_results" not in st.session_state:
        st.session_state.job_results = []
    
    if "last_poll_count" not in st.session_state:
        st.session_state.last_poll_count = 0
    
    if "search_complete" not in st.session_state:
        st.session_state.search_complete = False
    
    # Initialize batch counter in session state
    if "current_batch" not in st.session_state:
        st.session_state.current_batch = 0
    
    # Get user_id from session state (assuming it's stored after login)
    user_id = st.session_state.get("user_id", None)
    
    # Add a note about location
    if not search_location:
        st.info("💡 Pro tip: Adding a location (e.g., 'New York', 'London', 'Remote') helps find jobs that match your geographic preferences.")
    
    # Search button
    if st.button("Search Jobs") or (st.session_state.search_id and not st.session_state.search_complete):
        # Start a new search if we don't have a search_id
        if not st.session_state.search_id:
            with st.spinner("Starting job search..."):
                try:
                    # Prepare search query
                    response = requests.post(
                        f"{API_URL}/api/search/job-search",
                        json={
                            "target_roles": search_role,
                            "primary_skills": search_skills,
                            "location_preference": search_location,
                            "job_type": job_types,
                            "additional_preferences": preferences.get('additional_preferences', ''),
                            "user_id": user_id  # Add the user ID here
                        }
                    )
                    
                    if response.status_code == 200:
                        search_results = response.json()
                        st.session_state.job_results = search_results["jobs"]
                        st.session_state.search_id = search_results["search_id"]
                        st.session_state.search_complete = search_results.get("is_complete", False)
                        st.session_state.last_poll_count = len(search_results["jobs"])
                        
                        # Display initial results
                        job_count = len(search_results["jobs"])
                        st.success(f"Found {job_count} job{'s' if job_count != 1 else ''} matching your criteria!")
                        
                        if not st.session_state.search_complete:
                            st.info("Searching for more jobs in the background. Stay on this page to see new results.")
                    else:
                        st.error(f"Error searching for jobs: {response.text}")
                        st.session_state.search_id = None  # Reset to allow new search
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")
                    st.session_state.search_id = None  # Reset to allow new search
        
        # If we have a search_id and search is not complete, poll for more results
        elif not st.session_state.search_complete:
            try:
                # Poll for more results
                response = requests.get(f"{API_URL}/api/search/job-search/{st.session_state.search_id}")
                
                if response.status_code == 200:
                    search_results = response.json()
                    current_count = len(st.session_state.job_results)
                    new_count = len(search_results["jobs"])
                    
                    # Check if we have new jobs
                    if new_count > current_count:
                        # Get the latest batch number
                        if search_results["jobs"] and "batch" in search_results["jobs"][-1]:
                            latest_batch = search_results["jobs"][-1]["batch"]
                            if latest_batch > st.session_state.current_batch:
                                st.session_state.current_batch = latest_batch
                                st.info(f"Processing batch #{latest_batch} - found {new_count - current_count} new matching jobs")
                        
                        st.session_state.job_results = search_results["jobs"]
                    
                    # Check if search is complete
                    st.session_state.search_complete = search_results.get("is_complete", False)
                    
                    if st.session_state.search_complete:
                        st.success(f"Job search complete! Processed {st.session_state.current_batch} batches " +
                                   f"and found {new_count} matching jobs.")
                        
                        # Add a button to start a new search
                        if st.button("Start New Search"):
                            st.session_state.search_id = None
                            st.session_state.search_complete = False
                            st.session_state.current_batch = 0
                            st.rerun()
            
            except Exception as e:
                st.error(f"Error polling for results: {str(e)}")
        
        # Set a rerun to poll again automatically if search is not complete
        if st.session_state.search_id and not st.session_state.search_complete:
            time.sleep(2)  # Brief delay
            st.rerun()
    
    # Always display jobs if we have results
    if st.session_state.job_results:
        display_job_results()
    
    # Add button to cancel current search
    if st.session_state.search_id and not st.session_state.search_complete:
        if st.button("Stop Search"):
            st.session_state.search_complete = True
            st.success("Search stopped. Showing all jobs found so far.")

def display_job_results():
    """Display job search results in a nice format"""
    if not st.session_state.job_results:
        st.info("No job results to display yet.")
        return
    
    jobs = st.session_state.job_results
    
    st.write(f"### Job Results")
    st.write(f"Found {len(jobs)} jobs matching your skills")
    
    # Add sorting options
    sort_option = st.selectbox(
        "Sort by",
        options=["Skills Match", "Recent First", "Company"],
        index=0
    )
    
    # Sort the jobs based on selected option
    if sort_option == "Recent First":
        sorted_jobs = sorted(
            jobs, 
            key=lambda x: x.get("date_posted", ""), 
            reverse=True
        )
    elif sort_option == "Company":
        sorted_jobs = sorted(
            jobs,
            key=lambda x: x.get("company", "").lower()
        )
    else:  # Default to Skills Match
        sorted_jobs = sorted(
            jobs,
            key=lambda x: x.get("skills_matched", 0) / max(x.get("total_skills", 1), 1),
            reverse=True
        )
    
    # Add filtering options
    filter_company = st.text_input("Filter by company name")
    filter_location = st.text_input("Filter by location")
    
    # Apply filters
    filtered_jobs = sorted_jobs
    if filter_company:
        filtered_jobs = [
            job for job in filtered_jobs 
            if filter_company.lower() in job.get("company", "").lower()
        ]
    
    if filter_location:
        filtered_jobs = [
            job for job in filtered_jobs 
            if filter_location.lower() in job.get("location", "").lower()
        ]
    
    # Display count of filtered jobs
    if filter_company or filter_location:
        st.write(f"Showing {len(filtered_jobs)} jobs after filtering")
    
    # Display each job in a card-like format
    for i, job in enumerate(filtered_jobs):
        with st.container():
            # Job header
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.markdown(f"#### {i+1}. {job.get('title', 'Unknown Position')}")
                st.markdown(f"**{job.get('company', 'Unknown Company')}** • {job.get('location', 'Unknown')}")
            
            with col2:
                # Show skill match ratio
                skills_matched = job.get("skills_matched", 0)
                total_skills = job.get("total_skills", 1)
                match_percentage = int((skills_matched / total_skills) * 100)
                st.markdown(f"**Skills Match: {match_percentage}%**")
                st.markdown(f"**{job.get('job_type', '')}**")
            
            # Job details in expander
            with st.expander("View Details"):
                st.markdown(f"**Posted:** {job.get('date_posted', 'Unknown')}")
                
                if job.get('salary'):
                    st.markdown(f"**Salary:** {job.get('salary')}")
                
                st.markdown("**Description:**")
                st.markdown(job.get('description', 'No description available'))
                
                if job.get('url'):
                    st.markdown(f"[Apply for this job]({job.get('url')})")
            
            # Visual separator between jobs
            st.markdown("---")
