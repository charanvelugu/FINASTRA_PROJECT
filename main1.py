import streamlit as st
import os
import requests
from dotenv import load_dotenv
import google.generativeai as genai
from typing import Optional, Dict, List, Any
import base64
import time

# Load environment variables and configure API
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    st.error("Please set GOOGLE_API_KEY in your .env file")
    st.stop()

genai.configure(api_key=GOOGLE_API_KEY)

class DocumentationPrompts:
    @staticmethod
    def get_analysis_prompt(file_content: str, file_name: str, file_type: str) -> str:
        return f"""Analyze this {file_type} file '{file_name}' and provide comprehensive documentation:

1. OVERVIEW
- Purpose: Main functionality and goals
- Key Features: Primary capabilities
- Target Users: Intended audience
- Dependencies: Required libraries and versions

2. TECHNICAL DETAILS
- Architecture: Overall structure and patterns
- Components: Major classes and functions
- Data Flow: How data moves through the system
- Integration: External system connections

3. IMPLEMENTATION
- Key Functions: Important methods with parameters
- Data Structures: Main data organizations
- Error Handling: How errors are managed
- Configuration: Required settings

4. USAGE GUIDE
- Setup: Installation requirements
- Configuration: Environment setup
- Examples: Usage examples with code
- Common Cases: Typical use scenarios

5. IMPROVEMENTS
- Suggestions: Potential enhancements
- Security: Security considerations
- Performance: Optimization opportunities
- Maintenance: Code maintainability tips

CODE:
{file_content}
"""

class GitHubAPI:
    def __init__(self, token: Optional[str] = None):
        self.headers = {"Accept": "application/vnd.github.v3+json"}
        if token:
            self.headers["Authorization"] = f"token {token}"
    
    def parse_url(self, url: str) -> tuple[str, str]:
        """Extract owner and repo from GitHub URL."""
        parts = url.replace("https://github.com/", "").replace(".git", "").split("/")
        if len(parts) >= 2:
            return parts[0], parts[1]
        raise ValueError("Invalid GitHub URL format")

    def get_repository_content(self, owner: str, repo: str, path: str = "") -> List[Dict[str, Any]]:
        """Fetch repository contents."""
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def get_file_content(self, url: str) -> Optional[str]:
        """Fetch and decode file content."""
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            content = response.json()
            if content.get("encoding") == "base64":
                return base64.b64decode(content["content"]).decode('utf-8')
            return None
        except Exception as e:
            st.error(f"Error fetching file: {str(e)}")
            return None

class DocumentationGenerator:
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.prompts = DocumentationPrompts()
        self.supported_extensions = {'.py', '.js', '.java', '.cpp', '.ts', '.html', '.css', '.md'}

    def generate_documentation(self, content: str, file_name: str) -> Optional[str]:
        """Generate documentation for a file."""
        try:
            file_type = os.path.splitext(file_name)[1][1:]  # Get extension without dot
            prompt = self.prompts.get_analysis_prompt(content, file_name, file_type)
            response = self.model.generate_content([prompt])
            return response.text
        except Exception as e:
            st.error(f"Error generating documentation for {file_name}: {str(e)}")
            return None

    def is_supported_file(self, file_name: str) -> bool:
        """Check if file type is supported."""
        return any(file_name.endswith(ext) for ext in self.supported_extensions)

def main():
    st.set_page_config(
        page_title="GitHub Code Documentation Generator",
        page_icon="📚",
        layout="wide"
    )

    st.title("📚 GitHub Code Documentation Generator")
    st.markdown("""
    Generate comprehensive documentation for GitHub repositories using AI.
    """)

    # Sidebar configuration
    with st.sidebar:
        st.header("Configuration")
        github_token = st.text_input("GitHub Token (Optional)", type="password")
        st.markdown("*Token enables access to private repositories*")
        
        st.header("Supported Files")
        st.markdown("""
        - Python (.py)
        - JavaScript (.js)
        - TypeScript (.ts)
        - Java (.java)
        - C++ (.cpp)
        - HTML (.html)
        - CSS (.css)
        - Markdown (.md)
        """)

    # Main content area
    repo_url = st.text_input(
        "GitHub Repository URL",
        placeholder="https://github.com/username/repository"
    )

    if st.button("Generate Documentation", type="primary"):
        if not repo_url:
            st.warning("Please enter a GitHub repository URL")
            return

        try:
            # Initialize components
            github_api = GitHubAPI(github_token)
            doc_generator = DocumentationGenerator()

            # Process repository
            with st.spinner("Analyzing repository..."):
                # Get repository details
                owner, repo = github_api.parse_url(repo_url)
                st.info(f"Analyzing repository: {owner}/{repo}")

                # Fetch repository contents
                contents = github_api.get_repository_content(owner, repo)
                
                # Process files
                documentation = []
                for item in contents:
                    if item['type'] == 'file' and doc_generator.is_supported_file(item['name']):
                        with st.spinner(f"Processing {item['name']}..."):
                            content = github_api.get_file_content(item['url'])
                            if content:
                                doc = doc_generator.generate_documentation(content, item['name'])
                                if doc:
                                    documentation.append((item['name'], doc))
                                time.sleep(1)  # Rate limiting

                # Display results
                if documentation:
                    st.success("Documentation generated successfully!")
                    
                    # Create tabs for each file
                    for file_name, doc in documentation:
                        with st.expander(f"📄 {file_name}"):
                            st.markdown(doc)
                    
                    # Export option
                    combined_doc = "\n\n".join([f"# {name}\n{doc}" for name, doc in documentation])
                    st.download_button(
                        "📥 Download Complete Documentation",
                        combined_doc,
                        file_name="repository_documentation.md",
                        mime="text/markdown"
                    )
                else:
                    st.warning("No supported files found in the repository")

        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            st.markdown("Please check:\n- Repository URL is correct\n- Repository is public or token has access\n- Repository contains supported file types")

if __name__ == "__main__":
    main()