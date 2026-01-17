#!/usr/bin/env python3
"""
AI Utilities for GitHub Automation
Handles configuration, prompt templates, and AI client management
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, Union
import yaml

try:
    from openai import OpenAI
    from anthropic import Anthropic
except ImportError as e:
    print(f"Error: Missing required package: {e}")
    sys.exit(1)


class AIClient:
    """Unified AI client that handles multiple providers with configuration"""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self._find_config_file()
        self.config = self._load_config()
        self.prompts_dir = Path(self.config_path).parent / "prompts"

        # Initialize clients
        self.clients = {}
        self.active_provider = None
        self._setup_clients()

        # Usage tracking
        self.usage_stats = {
            'requests': 0,
            'tokens_used': 0,
            'estimated_cost': 0.0
        }

    def _find_config_file(self) -> str:
        """Find the config file in the scripts directory"""
        script_dir = Path(__file__).parent
        config_file = script_dir / "ai_config.yml"

        if not config_file.exists():
            raise FileNotFoundError(f"AI config file not found: {config_file}")

        return str(config_file)

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)

            if self.config_path.endswith('ai_config.yml'):
                print("✓ AI configuration loaded")

            return config
        except Exception as e:
            print(f"Error loading config: {e}")
            # Return minimal fallback config
            return {
                'provider_priority': ['openai', 'anthropic'],
                'providers': {
                    'openai': {'default_model': 'gpt-4o-mini'},
                    'anthropic': {'default_model': 'claude-3-5-haiku-20241022'}
                },
                'task_models': {},
                'fallback': {'on_failure': 'rule_based'}
            }

    def _setup_clients(self):
        """Initialize AI clients based on available API keys"""
        for provider in self.config.get('provider_priority', []):
            if provider == 'openai':
                api_key = os.environ.get('OPENAI_API_KEY')
                if api_key:
                    try:
                        self.clients['openai'] = OpenAI(api_key=api_key)
                        if not self.active_provider:
                            self.active_provider = 'openai'
                        print("✓ OpenAI client initialized")
                    except Exception as e:
                        print(f"Warning: OpenAI client failed: {e}")

            elif provider == 'anthropic':
                api_key = os.environ.get('ANTHROPIC_API_KEY')
                if api_key:
                    try:
                        self.clients['anthropic'] = Anthropic(api_key=api_key)
                        if not self.active_provider:
                            self.active_provider = 'anthropic'
                        print("✓ Anthropic client initialized")
                    except Exception as e:
                        print(f"Warning: Anthropic client failed: {e}")

        if not self.active_provider:
            print("Warning: No AI providers available. Using fallback behavior.")

    def load_prompt_template(self, template_name: str) -> Dict[str, Any]:
        """Load a prompt template from the prompts directory"""
        template_file = self.prompts_dir / f"{template_name}.yml"

        if not template_file.exists():
            raise FileNotFoundError(f"Prompt template not found: {template_file}")

        try:
            with open(template_file, 'r') as f:
                template = yaml.safe_load(f)
            return template
        except Exception as e:
            raise ValueError(f"Error loading template {template_name}: {e}")

    def render_prompt(self, template_name: str, variables: Dict[str, Any]) -> Dict[str, str]:
        """Render a prompt template with variables"""
        template = self.load_prompt_template(template_name)

        system_prompt = template.get('system_prompt', '').format(**variables)
        user_prompt = template.get('user_prompt', '').format(**variables)

        return {
            'system': system_prompt,
            'user': user_prompt,
            'template': template
        }

    def get_model_for_task(self, task_name: str, provider: Optional[str] = None) -> str:
        """Get the appropriate model for a specific task"""
        provider = provider or self.active_provider

        if not provider or provider not in self.config.get('providers', {}):
            return None

        # Get task complexity
        task_config = self.config.get('task_models', {}).get(task_name, {})
        complexity = task_config.get('complexity', 'standard')

        # Get model for complexity level
        provider_config = self.config['providers'][provider]
        models = provider_config.get('models', {})

        return models.get(complexity, provider_config.get('default_model'))

    def get_model_parameters(self, model: str, provider: str) -> Dict[str, Any]:
        """Get parameters for a specific model"""
        provider_config = self.config.get('providers', {}).get(provider, {})
        parameters = provider_config.get('parameters', {}).get(model, {})

        # Set defaults if not specified
        defaults = {
            'max_tokens': 1500,
            'temperature': 0.3,
            'timeout': 30
        }

        return {**defaults, **parameters}

    def estimate_cost(self, provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate the cost of an API call"""
        try:
            pricing = self.config['providers'][provider]['pricing'][model]
            input_cost = (input_tokens / 1000) * pricing['input']
            output_cost = (output_tokens / 1000) * pricing['output']
            return input_cost + output_cost
        except (KeyError, TypeError):
            return 0.0

    def call_ai(self, task_name: str, template_variables: Dict[str, Any],
                provider: Optional[str] = None) -> Dict[str, Any]:
        """Make an AI API call using task configuration and prompt templates"""

        provider = provider or self.active_provider
        if not provider or provider not in self.clients:
            return self._fallback_response(task_name)

        try:
            # Load and render prompt
            prompt_data = self.render_prompt(task_name, template_variables)

            # Get model and parameters
            model = self.get_model_for_task(task_name, provider)
            if not model:
                return self._fallback_response(task_name)

            params = self.get_model_parameters(model, provider)

            # Add template-specific parameters
            template_params = prompt_data['template'].get('parameters', {})
            params.update(template_params)

            # Make API call
            result = self._make_api_call(provider, model, prompt_data, params)

            # Track usage
            self.usage_stats['requests'] += 1
            if 'usage' in result:
                self.usage_stats['tokens_used'] += result['usage'].get('total_tokens', 0)
                cost = self.estimate_cost(
                    provider, model,
                    result['usage'].get('prompt_tokens', 0),
                    result['usage'].get('completion_tokens', 0)
                )
                self.usage_stats['estimated_cost'] += cost

            return result

        except Exception as e:
            print(f"AI call failed for {task_name}: {e}")
            return self._fallback_response(task_name)

    def _make_api_call(self, provider: str, model: str, prompt_data: Dict[str, str],
                       params: Dict[str, Any]) -> Dict[str, Any]:
        """Make the actual API call to the AI provider"""

        if provider == 'openai':
            client = self.clients['openai']

            # Prepare messages
            messages = []
            if prompt_data['system']:
                messages.append({"role": "system", "content": prompt_data['system']})
            messages.append({"role": "user", "content": prompt_data['user']})

            # Filter parameters for OpenAI
            openai_params = {
                'model': model,
                'messages': messages,
                'max_tokens': params.get('max_tokens', 1500),
                'temperature': params.get('temperature', 0.3)
            }

            # Add response format if specified
            if 'response_format' in params:
                openai_params['response_format'] = params['response_format']

            response = client.chat.completions.create(**openai_params)

            return {
                'content': response.choices[0].message.content,
                'model': model,
                'provider': provider,
                'usage': {
                    'prompt_tokens': response.usage.prompt_tokens,
                    'completion_tokens': response.usage.completion_tokens,
                    'total_tokens': response.usage.total_tokens
                }
            }

        elif provider == 'anthropic':
            client = self.clients['anthropic']

            # Prepare messages
            messages = [{"role": "user", "content": prompt_data['user']}]

            # Filter parameters for Anthropic
            anthropic_params = {
                'model': model,
                'messages': messages,
                'max_tokens': params.get('max_tokens', 1500),
                'temperature': params.get('temperature', 0.3)
            }

            # Add system prompt if available
            if prompt_data['system']:
                anthropic_params['system'] = prompt_data['system']

            response = client.messages.create(**anthropic_params)

            return {
                'content': response.content[0].text,
                'model': model,
                'provider': provider,
                'usage': {
                    'prompt_tokens': response.usage.input_tokens,
                    'completion_tokens': response.usage.output_tokens,
                    'total_tokens': response.usage.input_tokens + response.usage.output_tokens
                }
            }

        else:
            raise ValueError(f"Unsupported provider: {provider}")

    def _fallback_response(self, task_name: str) -> Dict[str, Any]:
        """Return a fallback response when AI is not available"""
        return {
            'content': None,
            'model': None,
            'provider': 'fallback',
            'error': 'AI provider not available',
            'task': task_name
        }

    def get_usage_summary(self) -> Dict[str, Any]:
        """Get a summary of usage statistics"""
        return {
            'requests_made': self.usage_stats['requests'],
            'total_tokens': self.usage_stats['tokens_used'],
            'estimated_cost_usd': round(self.usage_stats['estimated_cost'], 4),
            'active_provider': self.active_provider,
            'available_providers': list(self.clients.keys())
        }

    def log_debug_info(self):
        """Log debug information if enabled"""
        debug_config = self.config.get('debug', {})

        if debug_config.get('estimate_costs', True):
            usage = self.get_usage_summary()
            print(f"💰 Usage: {usage['requests_made']} requests, "
                  f"{usage['total_tokens']} tokens, "
                  f"~${usage['estimated_cost_usd']}")