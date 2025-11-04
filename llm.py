import os
import re
from typing import Dict, Optional, List
from openai import OpenAI
from anthropic import Anthropic
from constants import OPENAI_API_KEY, CLAUDE_API_KEY

class LLM:
    def __init__(self, model: str = "o3-mini", provider: Optional[str] = None):
        """
        Initialize LLM with OpenAI or Claude client.
        
        Args:
            model: Model name to use
            provider: Either 'openai' or 'claude'. If None, auto-detects based on available API keys.
        """
        self.model = model
        self.provider = None  # Will be set lazily
        self._requested_provider = provider.lower() if provider else None
        
        # Lazy initialization - clients will be created when first needed
        self.client = None
        self.claude_client = None
        self.should_reason = False
        
    def _initialize_client(self):
        """Lazy initialization of clients. Only called when actually needed."""
        if self.client is not None or self.claude_client is not None:
            return  # Already initialized
        
        # Determine which provider to use
        provider = self._requested_provider
        
        # If no provider specified, auto-detect based on available keys
        if not provider:
            if OPENAI_API_KEY:
                provider = "openai"
            elif CLAUDE_API_KEY:
                provider = "claude"
            else:
                raise ValueError("No API keys found. Please set either OPENAI_API_KEY or CLAUDE_API_KEY environment variable.")
        
        # Initialize the selected provider, with fallback if key not available
        if provider == "openai":
            if OPENAI_API_KEY:
                self.client = OpenAI(api_key=OPENAI_API_KEY)
                self.should_reason = self.model in ["o3-mini", "o1-preview"]
                self.claude_client = None
                self.provider = "openai"
            elif CLAUDE_API_KEY:
                # Fallback to Claude if OpenAI key not available
                self.claude_client = Anthropic(api_key=CLAUDE_API_KEY)
                self.client = None
                self.should_reason = False
                self.provider = "claude"
            else:
                raise ValueError("OPENAI_API_KEY not found. Please set the OPENAI_API_KEY environment variable.")
                
        elif provider == "claude":
            if CLAUDE_API_KEY:
                self.claude_client = Anthropic(api_key=CLAUDE_API_KEY)
                self.client = None
                self.should_reason = False
                self.provider = "claude"
            elif OPENAI_API_KEY:
                # Fallback to OpenAI if Claude key not available
                self.client = OpenAI(api_key=OPENAI_API_KEY)
                self.should_reason = self.model in ["o3-mini", "o1-preview"]
                self.claude_client = None
                self.provider = "openai"
            else:
                raise ValueError("CLAUDE_API_KEY not found. Please set the CLAUDE_API_KEY environment variable.")
        else:
            raise ValueError(f"Unknown provider: {provider}. Must be 'openai' or 'claude'")

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
        else:  # Claude
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
        else:  # Claude
            response = self.claude_client.messages.create(
                model=self.model,
                max_tokens=4096,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text

    