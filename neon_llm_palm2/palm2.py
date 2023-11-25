# NEON AI (TM) SOFTWARE, Software Development Kit & Application Development System
# All trademark and other rights reserved by their respective owners
# Copyright 2008-2021 Neongecko.com Inc.
# BSD-3
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from this
#    software without specific prior written permission.
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
# CONTRIBUTORS  BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA,
# OR PROFITS;  OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE,  EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import os
from vertexai.language_models import ChatModel, ChatMessage, TextEmbeddingModel
from openai.embeddings_utils import distances_from_embeddings

from typing import List, Dict
from neon_llm_core.llm import NeonLLM


class Palm2(NeonLLM):

    mq_to_llm_role = {
        "user": "user",
        "llm": "bot"
    }

    def __init__(self, config):
        super().__init__(config)
        self._embedding = None
        self.role = config["role"]
        self.context_depth = config["context_depth"]
        self.max_tokens = config["max_tokens"]
        self.api_key_path = config["key_path"]
        self.warmup()

    @property
    def tokenizer(self) -> None:
        return self._tokenizer

    @property
    def tokenizer_model_name(self) -> str:
        return ""

    @property
    def model(self) -> ChatModel:
        if self._model is None:
            self._model = ChatModel.from_pretrained("chat-bison@001")
        return self._model
    
    @property
    def embedding(self) -> TextEmbeddingModel:
        if self._embedding is None:
            self._embedding = TextEmbeddingModel.from_pretrained("textembedding-gecko@001")
        return self._embedding

    @property
    def llm_model_name(self) -> str:
        return self.model_name

    @property
    def _system_prompt(self) -> str:
        return self.role

    def warmup(self):
        self.model
        self.embedding

    def get_sorted_answer_indexes(self, question: str, answers: List[str], persona: dict) -> List[int]:
        """
            Creates sorted list of answer indexes with respect to order provided in :param answers based on PPL score
            Answers are sorted from best to worst
            :param question: incoming question
            :param answers: list of answers to rank
            :returns list of indexes
        """
        if not answers:
            return []
        scores = self._score(prompt=question, targets=answers, persona=persona)
        sorted_items = sorted(zip(range(len(answers)), scores), key=lambda x: x[1])
        sorted_items_indexes = [x[0] for x in sorted_items]
        return sorted_items_indexes

    def _call_model(self, prompt: Dict) -> str:
        """
            Wrapper for Palm2 Model generation logic
            :param prompt: Input messages sequence
            :returns: Output text sequence generated by model
        """

        chat = self._model.start_chat(
            context=prompt["system_prompt"],
            message_history=prompt["chat_history"],
            max_output_tokens=self.max_tokens,
            temperature=0,
        )
        response = chat.send_message(
            prompt["message"],
        )
        text = response.text

        return text

    def _assemble_prompt(self, message: str, chat_history: List[List[str]], persona: dict) -> List[Dict[str, str]]:
        """
            Assembles prompt engineering logic
            Setup Guidance:
            https://cloud.google.com/vertex-ai/docs/generative-ai/model-reference/overview

            :param message: Incoming prompt
            :param chat_history: History of preceding conversation
            :returns: assembled prompt
        """
        system_prompt = persona.get("description", self._system_prompt)
        # Context N messages
        messages = []
        for role, content in chat_history[-self.context_depth:]:
            role_palm2 = self.convert_role(role)
            messages.append(ChatMessage(content, role_palm2))
        prompt = {
            "system_prompt": system_prompt,
            "chat_history": messages,
            "message": message
        }

        return prompt

    def _score(self, prompt: str, targets: List[str], persona: dict) -> List[float]:
        """
            Calculates logarithmic probabilities for the list of provided text sequences
            :param prompt: Input text sequence
            :param targets: Output text sequences
            :returns: List of calculated logarithmic probabilities per output text sequence
        """

        question_embeddings, answers_embeddings = self._embeddings(question=prompt, answers=targets, persona=persona)
        scores_list = distances_from_embeddings(question_embeddings, answers_embeddings)
        return scores_list

    def _tokenize(self, prompt: str) -> None:
        pass

    def _embeddings(self, question: str, answers: List[str], persona: dict) -> (List[float], List[List[float]]):
        """
            Computes embeddings for the list of provided answers
            :param question: Question for LLM to response to
            :param answers: List of provided answers
            :returns ppl values for each answer
        """
        response = self.ask(question, [], persona=persona)
        texts = [response] + answers
        embeddings_obj = self._embedding.get_embeddings(texts)
        embeddings = [embedding.values for embedding in embeddings_obj]
        question_embeddings = embeddings[0]
        answers_embeddings = embeddings[1:]
        return question_embeddings, answers_embeddings