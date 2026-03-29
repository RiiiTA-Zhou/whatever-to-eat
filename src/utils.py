from openai import OpenAI
import re
import os
import subprocess
from dataclasses import dataclass

@dataclass
class LLMConfig:
    api_key: str
    llm_name: str = 'deepseek-chat'
    base_url: str = 'https://api.deepseek.com/v1'
    stop_words: str = '------'
    is_reasoning: bool = False

class OpenAIModel:
    '''call llm through openai api'''
    def __init__(self, llmconfig:LLMConfig, max_new_tokens = 1024, temp:float=0):
        self.api_key = llmconfig.api_key
        self.model = llmconfig.llm_name
        self.is_reasoning = llmconfig.is_reasoning
        self.stop_words = llmconfig.stop_words
        self.max_new_tokens = max_new_tokens
        self.temp = temp
        self.api_base_url = llmconfig.base_url

    def generate(self, prompt):
        client = OpenAI(api_key=self.api_key, base_url=self.api_base_url)
        if not self.is_reasoning:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt},
                ],
                stream=False,
                max_tokens= self.max_new_tokens,
                temperature= self.temp
            )
        else:   # if it is a reasoning model, then do not set max tokens
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt},
                ],
                stream=False,
                temperature= self.temp
            )
        return response.choices[0].message.content