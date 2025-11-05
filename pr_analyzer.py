"""
PR Analyzer - Analyzes GitHub Pull Requests for security vulnerabilities.

This module fetches PR data from GitHub, performs line-by-line analysis,
and then uses a security-focused agent to identify potential vulnerabilities.
"""

import os
import re
import json
import base64
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse
from github import Github
from github.Repository import Repository
from github.PullRequest import PullRequest
from llm import LLM
from logger import logger
from colorama import Fore


class PRAnalyzer:
    """
    Analyzes GitHub Pull Requests for security vulnerabilities.
    
    The analyzer works in two stages:
    1. Line-by-line analysis agent: Analyzes each changed line in detail
    2. Security analysis agent: Identifies security issues from the analysis
    """
    
    def __init__(self, pr_url: str, llm_model: str = "o3-mini", provider: str = "openai",
                 github_token: Optional[str] = None):
        """
        Initialize the PR Analyzer.
        
        Args:
            pr_url: GitHub PR URL (e.g., https://github.com/owner/repo/pull/123)
            llm_model: LLM model to use (default: o3-mini)
            provider: LLM provider ('openai' or 'claude')
            github_token: GitHub personal access token (optional, uses env var if not provided)
        """
        self.pr_url = pr_url
        self.llm_model = llm_model
        self.provider = provider
        
        # Initialize GitHub client
        github_token = github_token or os.environ.get("GITHUB_TOKEN")
        if not github_token:
            logger.warning(f"{Fore.YELLOW}No GITHUB_TOKEN found. Some operations may be rate-limited.")
        self.github = Github(github_token) if github_token else Github()
        
        # Parse PR URL
        self.owner, self.repo_name, self.pr_number = self._parse_pr_url(pr_url)
        logger.info(f"{Fore.CYAN}Parsed PR: {self.owner}/{self.repo_name}#{self.pr_number}")
        
        # Initialize LLM instances for both agents
        self.line_analyzer_llm = LLM(model=llm_model, provider=provider)
        self.security_analyzer_llm = LLM(model=llm_model, provider=provider)
        
        # PR data cache
        self.pr_data = None
        self.diff_data = None
        self.file_contents = {}
        
    def _parse_pr_url(self, url: str) -> Tuple[str, str, int]:
        """
        Parse GitHub PR URL to extract owner, repo, and PR number.
        
        Args:
            url: GitHub PR URL
            
        Returns:
            Tuple of (owner, repo_name, pr_number)
            
        Raises:
            ValueError: If URL format is invalid
        """
        # Pattern: https://github.com/owner/repo/pull/123
        pattern = r'github\.com/([^/]+)/([^/]+)/pull/(\d+)'
        match = re.search(pattern, url)
        
        if not match:
            raise ValueError(f"Invalid GitHub PR URL format: {url}")
        
        owner = match.group(1)
        repo_name = match.group(2)
        pr_number = int(match.group(3))
        
        return owner, repo_name, pr_number
    
    def fetch_pr_data(self) -> Dict:
        """
        Fetch PR data including diff and file contents.
        
        Returns:
            Dictionary containing PR metadata, diff, and file contents
        """
        logger.info(f"{Fore.GREEN}Fetching PR data from GitHub...")
        
        try:
            repo = self.github.get_repo(f"{self.owner}/{self.repo_name}")
            pr = repo.get_pull(self.pr_number)
            
            # Get PR metadata
            self.pr_data = {
                "title": pr.title,
                "body": pr.body or "",
                "author": pr.user.login,
                "state": pr.state,
                "created_at": pr.created_at.isoformat(),
                "updated_at": pr.updated_at.isoformat(),
                "base": pr.base.ref,
                "head": pr.head.ref,
                "changed_files": pr.changed_files,
                "additions": pr.additions,
                "deletions": pr.deletions,
            }
            
            logger.info(f"{Fore.GREEN}PR Title: {self.pr_data['title']}")
            logger.info(f"{Fore.GREEN}Changed files: {self.pr_data['changed_files']}")
            logger.info(f"{Fore.GREEN}Additions: {self.pr_data['additions']}, Deletions: {self.pr_data['deletions']}")
            
            # Get diff
            self.diff_data = pr.diff()
            
            # Get file contents for all changed files
            files = pr.get_files()
            for file in files:
                filename = file.filename
                
                # Get full file content from head commit
                try:
                    if file.status in ['added', 'modified', 'renamed']:
                        # Get file content from head branch
                        file_content = repo.get_contents(
                            filename, 
                            ref=pr.head.sha
                        )
                        if file_content.encoding == 'base64':
                            self.file_contents[filename] = base64.b64decode(file_content.content).decode('utf-8')
                        else:
                            self.file_contents[filename] = file_content.content
                    elif file.status == 'removed':
                        # Try to get from base branch
                        try:
                            file_content = repo.get_contents(
                                filename,
                                ref=pr.base.sha
                            )
                            if file_content.encoding == 'base64':
                                self.file_contents[filename] = base64.b64decode(file_content.content).decode('utf-8')
                            else:
                                self.file_contents[filename] = file_content.content
                        except:
                            self.file_contents[filename] = "[File was removed - content unavailable]"
                except Exception as e:
                    logger.warning(f"{Fore.YELLOW}Could not fetch content for {filename}: {e}")
                    self.file_contents[filename] = "[Content unavailable]"
            
            return {
                "pr_data": self.pr_data,
                "diff": self.diff_data,
                "file_contents": self.file_contents,
                "files": [f.filename for f in files]
            }
            
        except Exception as e:
            logger.error(f"{Fore.RED}Error fetching PR data: {e}")
            raise
    
    def _parse_diff(self, diff: str) -> List[Dict]:
        """
        Parse diff into structured format with line-by-line changes.
        
        Args:
            diff: Raw diff string
            
        Returns:
            List of dictionaries containing file changes with line numbers
        """
        parsed_changes = []
        current_file = None
        current_hunk = None
        line_number_old = None
        line_number_new = None
        
        lines = diff.split('\n')
        
        for line in lines:
            # File header: +++ b/path/to/file
            if line.startswith('+++ '):
                if current_file:
                    parsed_changes.append(current_file)
                current_file = {
                    "filename": line[6:].strip(),  # Remove '+++ b/'
                    "hunks": []
                }
                line_number_old = None
                line_number_new = None
                
            # Hunk header: @@ -old_start,old_count +new_start,new_count @@
            elif line.startswith('@@'):
                if current_file:
                    hunk_match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
                    if hunk_match:
                        line_number_old = int(hunk_match.group(1))
                        line_number_new = int(hunk_match.group(3))
                        current_hunk = {
                            "header": line,
                            "old_start": line_number_old,
                            "new_start": line_number_new,
                            "lines": []
                        }
                        current_file["hunks"].append(current_hunk)
                        
            # Changed lines
            elif current_hunk:
                if line.startswith(' '):
                    # Context line (unchanged)
                    current_hunk["lines"].append({
                        "type": "context",
                        "content": line[1:],
                        "old_line": line_number_old,
                        "new_line": line_number_new
                    })
                    if line_number_old is not None:
                        line_number_old += 1
                    if line_number_new is not None:
                        line_number_new += 1
                elif line.startswith('-'):
                    # Deleted line
                    current_hunk["lines"].append({
                        "type": "deleted",
                        "content": line[1:],
                        "old_line": line_number_old,
                        "new_line": None
                    })
                    if line_number_old is not None:
                        line_number_old += 1
                elif line.startswith('+'):
                    # Added line
                    current_hunk["lines"].append({
                        "type": "added",
                        "content": line[1:],
                        "old_line": None,
                        "new_line": line_number_new
                    })
                    if line_number_new is not None:
                        line_number_new += 1
        
        if current_file:
            parsed_changes.append(current_file)
        
        return parsed_changes
    
    def analyze_line_by_line(self, parsed_changes: List[Dict]) -> List[Dict]:
        """
        Analyze each changed line using the line-by-line analysis agent.
        
        Args:
            parsed_changes: Parsed diff structure
            
        Returns:
            List of analysis results for each file/change
        """
        logger.info(f"{Fore.GREEN}Starting line-by-line analysis...")
        
        analysis_results = []
        
        for file_change in parsed_changes:
            filename = file_change["filename"]
            logger.info(f"{Fore.CYAN}Analyzing file: {filename}")
            
            # Get full file content for context
            file_content = self.file_contents.get(filename, "")
            
            # Build context for analysis
            analysis_context = f"""
File: {filename}
Full File Content:
{file_content}

Changes in this file:
"""
            
            for hunk in file_change["hunks"]:
                analysis_context += f"\nHunk starting at line {hunk['new_start']}:\n"
                for line_info in hunk["lines"]:
                    line_type = line_info["type"]
                    content = line_info["content"]
                    line_num = line_info.get("new_line") or line_info.get("old_line")
                    
                    if line_type == "added":
                        analysis_context += f"  + Line {line_num}: {content}\n"
                    elif line_type == "deleted":
                        analysis_context += f"  - Line {line_num}: {content}\n"
                    elif line_type == "context":
                        analysis_context += f"    Line {line_num}: {content}\n"
            
            # Create prompt for line-by-line analysis
            line_analysis_prompt = f"""
You are a code review expert. Analyze the following code changes line by line.

{analysis_context}

For each changed line (marked with + or -), provide:
1. What the line does
2. Potential issues or concerns
3. Security implications
4. Code quality observations

Be thorough and specific. Focus on understanding the intent and context of each change.
"""
            
            # Get analysis from line analyzer agent
            try:
                analysis = self.line_analyzer_llm.prompt(line_analysis_prompt, temperature=0.2)
                analysis_results.append({
                    "filename": filename,
                    "analysis": analysis,
                    "changes": file_change
                })
                logger.info(f"{Fore.GREEN}Completed analysis for {filename}")
            except Exception as e:
                logger.error(f"{Fore.RED}Error analyzing {filename}: {e}")
                analysis_results.append({
                    "filename": filename,
                    "analysis": f"Error during analysis: {str(e)}",
                    "changes": file_change
                })
        
        return analysis_results
    
    def find_security_issues(self, line_analyses: List[Dict]) -> Dict:
        """
        Use security analysis agent to identify security issues from line-by-line analyses.
        
        Args:
            line_analyses: Results from line-by-line analysis
            
        Returns:
            Dictionary containing security findings
        """
        logger.info(f"{Fore.GREEN}Starting security analysis...")
        
        # Compile all analyses into a single context
        security_context = f"""
PR Title: {self.pr_data['title']}
PR Description: {self.pr_data['body']}
PR Author: {self.pr_data['author']}

Line-by-line analysis results:
"""
        
        for analysis_result in line_analyses:
            security_context += f"\n{'='*60}\n"
            security_context += f"File: {analysis_result['filename']}\n"
            security_context += f"{'='*60}\n"
            security_context += f"{analysis_result['analysis']}\n"
        
        # Create security analysis prompt
        security_prompt = f"""
You are a security expert specializing in vulnerability detection and code security analysis.

Review the following line-by-line code analysis and identify:

1. **Security Vulnerabilities**: 
   - Buffer overflows
   - SQL injection
   - XSS vulnerabilities
   - Command injection
   - Path traversal
   - Authentication/authorization issues
   - Cryptographic weaknesses
   - Input validation issues
   - Memory safety issues
   - Race conditions
   - Any other security concerns

2. **Severity Assessment**: For each issue found, assess:
   - Severity (Critical, High, Medium, Low)
   - Exploitability
   - Impact
   - Affected code locations

3. **Recommendations**: Provide specific remediation suggestions

4. **False Positives**: Note any items that might seem suspicious but are actually safe

{security_context}

Provide a comprehensive security analysis report in a structured format.
"""
        
        try:
            security_report = self.security_analyzer_llm.prompt(security_prompt, temperature=0.1)
            
            return {
                "pr_url": self.pr_url,
                "pr_title": self.pr_data['title'],
                "security_report": security_report,
                "line_analyses": line_analyses,
                "summary": {
                    "files_analyzed": len(line_analyses),
                    "total_changes": self.pr_data['additions'] + self.pr_data['deletions']
                }
            }
        except Exception as e:
            logger.error(f"{Fore.RED}Error in security analysis: {e}")
            raise
    
    def analyze(self) -> Dict:
        """
        Main analysis workflow: fetch PR data, analyze line-by-line, then find security issues.
        
        Returns:
            Complete analysis results including security findings
        """
        # Step 1: Fetch PR data
        pr_data = self.fetch_pr_data()
        
        # Step 2: Parse diff
        parsed_changes = self._parse_diff(self.diff_data)
        logger.info(f"{Fore.GREEN}Parsed {len(parsed_changes)} changed files")
        
        # Step 3: Line-by-line analysis
        line_analyses = self.analyze_line_by_line(parsed_changes)
        
        # Step 4: Security analysis
        security_results = self.find_security_issues(line_analyses)
        
        return security_results
    
    def save_results(self, results: Dict, output_file: str = "pr_security_analysis.json"):
        """
        Save analysis results to a JSON file.
        
        Args:
            results: Analysis results dictionary
            output_file: Output file path
        """
        output_path = os.path.join("results", output_file)
        os.makedirs("results", exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"{Fore.GREEN}Results saved to {output_path}")


def main():
    """
    Example usage of PRAnalyzer.
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyze GitHub PR for security vulnerabilities")
    parser.add_argument("-u", "--pr_url", help="GitHub PR URL (e.g., https://github.com/owner/repo/pull/123)")
    parser.add_argument("-m", "--model", default="o3-mini", help="LLM model to use")
    parser.add_argument("-p", "--provider", default="openai", choices=["openai", "claude", "gemini", "ollama"],
                       help="LLM provider")
    parser.add_argument("-o", "--output", default="pr_security_analysis.json",
                       help="Output file name")
    parser.add_argument("-t", "--token", help="GitHub personal access token (or set GITHUB_TOKEN env var)")
    
    args = parser.parse_args()
    
    # Initialize analyzer
    analyzer = PRAnalyzer(
        pr_url=args.pr_url,
        llm_model=args.model,
        provider=args.provider,
        github_token=args.token
    )
    
    # Run analysis
    results = analyzer.analyze()
    
    # Save results
    analyzer.save_results(results, args.output)
    
    # Print summary
    print(f"\n{Fore.GREEN}{'='*60}")
    print(f"Security Analysis Complete")
    print(f"{'='*60}")
    print(f"PR: {results['pr_url']}")
    print(f"Files analyzed: {results['summary']['files_analyzed']}")
    print(f"Total changes: {results['summary']['total_changes']}")
    print(f"\nSecurity Report:\n{results['security_report']}")


if __name__ == "__main__":
    main()

