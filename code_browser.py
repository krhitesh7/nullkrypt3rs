from clang.cindex import Index, CursorKind
import os
import re
from typing import Dict
from llm import LLM
from logger import logger
from colorama import Fore, Style

class CodeBrowser:
    def __init__(self, llm_model: str = "gpt-4o-mini", provider: str = None):
        """
        Initialize CodeBrowser.
        
        Args:
            llm_model: LLM model to use (default: "gpt-4o-mini")
            provider: LLM provider to use ('openai' or 'claude'). If None, auto-detects.
        """
        self.index = Index.create()
        # Use the provider from the agent, or auto-detect if not specified
        self.llm = LLM(model=llm_model, provider=provider)

    def get_class_body(self, filename: str, class_name: str) -> Dict:
        """
        Extract a class's body from a C source file using libclang.
        
        Args:
            filename: Path to the .c source file
            class_name: Name of class to extract
            
        Returns:
            Dict containing class details
        """
        if not os.path.exists(filename):
            raise FileNotFoundError(f"File not found: {filename}")

        # Parse the source file with C++ language options
        tu = self.index.parse(filename, args=['-x', 'c++'])
        if not tu:
            raise ValueError(f"Failed to parse {filename}")

        # Find the target class
        class_node = None
        for node in tu.cursor.walk_preorder():
            if (node.kind == CursorKind.CLASS_DECL and 
                node.spelling == class_name):
                class_node = node
                break

        if not class_node:
            raise ValueError(f"Class '{class_name}' not found in {filename}")

        # Get the class's source range
        start = class_node.extent.start
        end = class_node.extent.end
        
        # Read the original file to get the complete source
        with open(filename, 'r') as f:
            file_lines = f.readlines()

        # Extract class lines with line numbers
        class_lines = file_lines[start.line-1:end.line]
        numbered_lines = [
            f"{i+start.line}: {line.rstrip()}"
            for i, line in enumerate(class_lines)
        ]

        # Match original format
        return {
            'filename': filename,
            'name': class_name,
            'type': 'class',
            'source': '\n'.join(numbered_lines),
            'lines': [line.strip() for line in class_lines if line.strip()]
        }

    def _extract_function_text_based(self, filename: str, function_name: str) -> Dict:
        """
        Extract a function's body using text-based parsing (for non-C/C++ languages).
        
        Args:
            filename: Path to the source file
            function_name: Name of function to extract
            
        Returns:
            Dict containing function details
        """
        if not os.path.exists(filename):
            raise FileNotFoundError(f"File not found: {filename}")
        
        with open(filename, 'r') as f:
            file_lines = f.readlines()
        
        # Try to find the function using regex patterns for different languages
        function_patterns = [
            # Go: func functionName(...)
            rf'\b(func\s+\w+\s+)?{re.escape(function_name)}\s*\(',
            # Python: def functionName(...)
            rf'\bdef\s+{re.escape(function_name)}\s*\(',
            # Java/C#: functionName(...) {
            rf'\b{re.escape(function_name)}\s*\([^)]*\)\s*{{',
            # Rust: fn function_name(...)
            rf'\bfn\s+{re.escape(function_name)}\s*\(',
        ]
        
        start_line = None
        for i, line in enumerate(file_lines):
            for pattern in function_patterns:
                if re.search(pattern, line):
                    start_line = i
                    break
            if start_line is not None:
                break
        
        if start_line is None:
            raise ValueError(f"Function '{function_name}' not found in {filename}")
        
        # Find the function end by counting braces
        brace_count = 0
        in_function = False
        end_line = start_line
        
        for i in range(start_line, len(file_lines)):
            line = file_lines[i]
            for char in line:
                if char == '{':
                    brace_count += 1
                    in_function = True
                elif char == '}':
                    brace_count -= 1
                    if in_function and brace_count == 0:
                        end_line = i
                        break
            if in_function and brace_count == 0:
                break
        
        if end_line == start_line:
            # If we couldn't find the end, include the next 50 lines or until end of file
            end_line = min(start_line + 50, len(file_lines) - 1)
        
        # Extract function lines with line numbers
        function_lines = file_lines[start_line:end_line + 1]
        numbered_lines = [
            f"{i+start_line+1}: {line.rstrip()}"
            for i, line in enumerate(function_lines)
        ]
        
        return {
            'filename': filename,
            'name': function_name,
            'type': 'function',
            'source': '\n'.join(numbered_lines),
            'lines': [line.strip() for line in function_lines if line.strip()]
        }

    def get_function_body(self, filename: str, function_name: str) -> Dict:
        """
        Extract a function's body from a source file.
        Uses libclang for C/C++ files, text-based parsing for other languages.
        
        Args:
            filename: Path to the source file
            function_name: Name of function to extract
            
        Returns:
            Dict containing function details
        """
        if not os.path.exists(filename):
            raise FileNotFoundError(f"File not found: {filename}")

        # For .h files, return the full file
        if filename.endswith('.h'):
            with open(filename, 'r') as f:
                file_lines = f.readlines()
            numbered_lines = [
                f"{i+1}: {line.rstrip()}" 
                for i, line in enumerate(file_lines)
            ]
            return {
                'filename': filename,
                'name': function_name,
                'type': 'header',
                'source': '\n'.join(numbered_lines),
                'lines': [line.strip() for line in file_lines if line.strip()]
            }

        # For C/C++ files, use libclang
        if filename.endswith('.c') or filename.endswith('.cpp'):
            try:
                # Parse the source file
                tu = self.index.parse(filename)
                if not tu:
                    raise ValueError(f"Failed to parse {filename}")

                # Find the target function
                function_node = None
                for node in tu.cursor.walk_preorder():
                    if ((node.kind == CursorKind.FUNCTION_DECL or node.kind == CursorKind.CXX_METHOD) and 
                            node.spelling == function_name):
                        function_node = node
                        break

                if not function_node:
                    try:
                        class_node = self.get_class_body(filename, function_name)
                        return class_node
                    except ValueError:
                        pass  # Fall through to text-based extraction

                if function_node:
                    # Get the function's source range
                    start = function_node.extent.start
                    end = function_node.extent.end
                    
                    # Read the original file to get the complete source
                    with open(filename, 'r') as f:
                        file_lines = f.readlines()

                    # Extract function lines with line numbers
                    function_lines = file_lines[start.line-1:end.line]
                    numbered_lines = [
                        f"{i+start.line}: {line.rstrip()}"
                        for i, line in enumerate(function_lines)
                    ]

                    return {
                        'filename': filename,
                        'name': function_name,
                        'type': 'function',
                        'source': '\n'.join(numbered_lines),
                        'lines': [line.strip() for line in function_lines if line.strip()]
                    }
            except Exception as e:
                logger.info(f"{Fore.YELLOW}libclang parsing failed, falling back to text-based extraction: {e}{Style.RESET_ALL}")
                # Fall through to text-based extraction
        
        # For other languages (Go, Python, Rust, etc.), use text-based extraction
        return self._extract_function_text_based(filename, function_name)

    def code_browser_source(self, file: str, name: str) -> str:
        """
        Analyze a function from a specific C source file.
        
        Args:
            file: Path to the .c file to analyze
            name: Name of function to analyze
            
        Returns:
            String containing the function source with line numbers
        """
        try:
            function_details = self.get_function_body(file, name)
            return function_details['source']
        except (ValueError, FileNotFoundError) as e:
            return str(e)

    