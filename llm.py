import os
import re
from typing import Dict, Optional, List
from openai import OpenAI
from anthropic import Anthropic
import google.generativeai as genai
import ollama
from constants import OPENAI_API_KEY, CLAUDE_API_KEY, GEMINI_API_KEY, OLLAMA_BASE_URL

class LLM:
    def __init__(self, model: str = "o3-mini", provider: Optional[str] = None):
        """
        Initialize LLM with OpenAI, Claude, Gemini, or Ollama client.
        
        Args:
            model: Model name to use
            provider: Either 'openai', 'claude', 'gemini', or 'ollama'. If None, auto-detects based on available API keys.
        """
        self.model = model
        self.provider = None  # Will be set lazily
        self._requested_provider = provider.lower() if provider else None
        
        # Lazy initialization - clients will be created when first needed
        self.client = None
        self.claude_client = None
        self.gemini_client = None
        self.ollama_client = None
        self.should_reason = False
        
    def _initialize_client(self):
        """Lazy initialization of clients. Only called when actually needed."""
        if self.client is not None or self.claude_client is not None or self.gemini_client is not None or self.ollama_client is not None:
            return  # Already initialized
        
        # Determine which provider to use
        provider = self._requested_provider
        
        # If no provider specified, auto-detect based on available keys
        if not provider:
            if OPENAI_API_KEY:
                provider = "openai"
            elif CLAUDE_API_KEY:
                provider = "claude"
            elif GEMINI_API_KEY:
                provider = "gemini"
            else:
                # Default to Ollama if no API keys are set
                provider = "ollama"
        
        # Initialize the selected provider, with fallback if key not available
        if provider == "openai":
            if OPENAI_API_KEY:
                self.client = OpenAI(api_key=OPENAI_API_KEY)
                self.should_reason = self.model in ["o3-mini", "o1-preview"]
                self.claude_client = None
                self.gemini_client = None
                self.ollama_client = None
                self.provider = "openai"
            elif CLAUDE_API_KEY:
                # Fallback to Claude if OpenAI key not available
                self.claude_client = Anthropic(api_key=CLAUDE_API_KEY)
                self.client = None
                self.gemini_client = None
                self.ollama_client = None
                self.should_reason = False
                self.provider = "claude"
            elif GEMINI_API_KEY:
                # Fallback to Gemini if OpenAI and Claude keys not available
                genai.configure(api_key=GEMINI_API_KEY)
                self.gemini_client = genai.GenerativeModel(self.model)
                self.client = None
                self.claude_client = None
                self.ollama_client = None
                self.should_reason = False
                self.provider = "gemini"
            else:
                # Fallback to Ollama if no keys available
                self.ollama_client = ollama.Client(host=OLLAMA_BASE_URL)
                self.client = None
                self.claude_client = None
                self.gemini_client = None
                self.should_reason = False
                self.provider = "ollama"
                
        elif provider == "claude":
            if CLAUDE_API_KEY:
                self.claude_client = Anthropic(api_key=CLAUDE_API_KEY)
                self.client = None
                self.gemini_client = None
                self.ollama_client = None
                self.should_reason = False
                self.provider = "claude"
            elif OPENAI_API_KEY:
                # Fallback to OpenAI if Claude key not available
                self.client = OpenAI(api_key=OPENAI_API_KEY)
                self.should_reason = self.model in ["o3-mini", "o1-preview"]
                self.claude_client = None
                self.gemini_client = None
                self.ollama_client = None
                self.provider = "openai"
            elif GEMINI_API_KEY:
                # Fallback to Gemini if Claude and OpenAI keys not available
                genai.configure(api_key=GEMINI_API_KEY)
                self.gemini_client = genai.GenerativeModel(self.model)
                self.client = None
                self.claude_client = None
                self.ollama_client = None
                self.should_reason = False
                self.provider = "gemini"
            else:
                # Fallback to Ollama if no keys available
                self.ollama_client = ollama.Client(host=OLLAMA_BASE_URL)
                self.client = None
                self.claude_client = None
                self.gemini_client = None
                self.should_reason = False
                self.provider = "ollama"
        
        elif provider == "gemini":
            if GEMINI_API_KEY:
                genai.configure(api_key=GEMINI_API_KEY)
                self.gemini_client = genai.GenerativeModel(self.model)
                self.client = None
                self.claude_client = None
                self.ollama_client = None
                self.should_reason = False
                self.provider = "gemini"
            elif OPENAI_API_KEY:
                # Fallback to OpenAI if Gemini key not available
                self.client = OpenAI(api_key=OPENAI_API_KEY)
                self.should_reason = self.model in ["o3-mini", "o1-preview"]
                self.claude_client = None
                self.gemini_client = None
                self.ollama_client = None
                self.provider = "openai"
            elif CLAUDE_API_KEY:
                # Fallback to Claude if Gemini and OpenAI keys not available
                self.claude_client = Anthropic(api_key=CLAUDE_API_KEY)
                self.client = None
                self.gemini_client = None
                self.ollama_client = None
                self.should_reason = False
                self.provider = "claude"
            else:
                # Fallback to Ollama if no keys available
                self.ollama_client = ollama.Client(host=OLLAMA_BASE_URL)
                self.client = None
                self.claude_client = None
                self.gemini_client = None
                self.should_reason = False
                self.provider = "ollama"
        
        elif provider == "ollama":
            # Ollama doesn't require an API key, just a base URL
            self.ollama_client = ollama.Client(host=OLLAMA_BASE_URL)
            self.should_reason = self.model in ["qwen3:235b"]
            self.client = None
            self.claude_client = None
            self.gemini_client = None
            self.should_reason = False
            self.provider = "ollama"
        
        else:
            raise ValueError(f"Unknown provider: {provider}. Must be 'openai', 'claude', 'gemini', or 'ollama'")

    def _convert_messages_for_claude(self, messages: List[Dict]) -> List[Dict]:
        """Convert OpenAI format messages to Claude format."""
        claude_messages = []
        system_message = None
        
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                system_message = content
            elif role in ["user", "assistant"]:
                claude_messages.append({"role": role, "content": content})
        
        return claude_messages, system_message
    
    def _convert_messages_for_gemini(self, messages: List[Dict]) -> tuple:
        """Convert OpenAI format messages to Gemini format."""
        gemini_messages = []
        system_instruction = None
        
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                system_instruction = content
            elif role == "user":
                gemini_messages.append({"role": "user", "parts": [content]})
            elif role == "assistant":
                gemini_messages.append({"role": "model", "parts": [content]})
        
        return gemini_messages, system_instruction

    def action(self, messages, reasoning: str = "medium", temperature: float = 0.0):
        """Execute an action using the selected provider."""
        self._initialize_client()  # Ensure client is initialized
        
        if self.provider == "openai":
            if not self.should_reason:
                response = self.client.chat.completions.create(
                    model=self.model,
                    temperature=temperature,
                    messages=messages,
                )
                return response.choices[0].message.content
            else:
                response = self.client.chat.completions.create(
                    model=self.model,
                    reasoning_effort=reasoning,
                    messages=messages,
                )
                return response.choices[0].message.content
        
        elif self.provider == "claude":
            claude_messages, system_message = self._convert_messages_for_claude(messages)
            params = {
                "model": self.model,
                "max_tokens": 4096,
                "temperature": temperature,
                "messages": claude_messages,
            }
            if system_message:
                params["system"] = system_message
            
            response = self.claude_client.messages.create(**params)
            return response.content[0].text
        
        elif self.provider == "gemini":  # Gemini
            gemini_messages, system_instruction = self._convert_messages_for_gemini(messages)

            print(f"================= Gemini messages: {gemini_messages}")
            
            # Create a new model instance with system instruction if provided
            if system_instruction:
                model = genai.GenerativeModel(
                    model_name=self.model,
                    system_instruction=system_instruction
                )
            else:
                model = self.gemini_client
            
            # Start a chat session with history
            chat = model.start_chat(history=gemini_messages[:-1] if len(gemini_messages) > 1 else [])
            
            # Send the last message
            last_non_empty_message = ""
            for message in reversed(gemini_messages):
                if message["parts"] and len(message["parts"]) > 0 and message["parts"][0] != "":
                    last_non_empty_message = message["parts"][0]
                    break
            last_message = last_non_empty_message

            if last_message == "":
                return "No response from Gemini"
            
            response = chat.send_message(
                last_message,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=4096,
                )
            )
            return response.text
        
        else:  # Ollama
            print(f"================= Ollama model: {self.model} {self.should_reason}")
            response = self.ollama_client.chat(
                model=self.model,
                messages=messages,
                options={
                    "temperature": temperature,
                    "num_predict": 16384,
                },
                think=self.should_reason
            )
            return response['message']['content']

    def prompt(self, prompt: str, reasoning: str = "medium", temperature: float = 0.2):
        """Send a prompt using the selected provider."""
        self._initialize_client()  # Ensure client is initialized
        
        if self.provider == "openai":
            if not self.should_reason:
                response = self.client.chat.completions.create(
                    model=self.model,
                    temperature=temperature,
                    messages=[{"role": "user", "content": prompt}],
                )
                return response.choices[0].message.content
            else:
                response = self.client.chat.completions.create(
                    model=self.model,
                    reasoning_effort=reasoning,
                    messages=[{"role": "user", "content": prompt}],
                )
                return response.choices[0].message.content
        
        elif self.provider == "claude":
            response = self.claude_client.messages.create(
                model=self.model,
                max_tokens=4096,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        
        elif self.provider == "gemini":
            response = self.gemini_client.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=4096,
                )
            )
            return response.text
        
        else:  # Ollama
            print(f"================= Ollama model: {self.model} {self.should_reason}")
            response = self.ollama_client.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                options={
                    "temperature": temperature,
                    "num_predict": 16384,
                },
                think=self.should_reason
            )
            return response['message']['content']

    