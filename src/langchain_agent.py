"""
LangChain Agent skeleton for "随便：今天吃什么".

Design goals:
1) Normalize user input into strict JSON (UserInput) using structured output.
2) Load local memory (preferences + recent meals) and inject into prompt.
3) Branch by mode (delivery / dine_in / cook) and generate strict JSON Output.
4) Post-process and update memory.

Note: This file provides an implementation blueprint. You can replace the placeholder
candidate generation / scoring parts with real data sources (APIs / local recipes DB).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_openai import ChatOpenAI
from langchain_core.pydantic_v1 import BaseModel, Field


# -----------------------------
# Pydantic models (approx schema)
# -----------------------------

Mode = Literal["delivery", "dine_in", "cook"]


class NutritionTags(BaseModel):
    protein: Union[str, List[str]]
    veg: Union[str, List[str]]
    carbs: Union[str, List[str]]
    fat: Union[str, List[str]]


class UserInput(BaseModel):
    id: Optional[str] = None
    mode: Mode
    people_count: Optional[int] = Field(default=None, ge=1)
    time: Optional[Literal["noon", "evening", "midnight"]] = None
    budget: Optional[float] = Field(default=None, ge=0, le=1000)
    location: Optional[str] = None
    constraints: Optional[str] = None
    liked_flavors: Optional[Union[str, List[str]]] = None
    disliked_flavors: Optional[Union[str, List[str]]] = None
    diet_restrictions: Optional[Union[str, List[str]]] = None
    cooking_skill: Optional[int] = Field(default=None, ge=0, le=3)
    rating_last: Optional[Literal["like", "neutral", "dislike"]] = None
    history_window: Optional[str] = None
    history_entries: Optional[List[Dict[str, Any]]] = None
    candidate_pool_json: Optional[List[Dict[str, Any]]] = None


class MainRecommendationDelivery(BaseModel):
    provider_name: str
    dish_name_or_category: str
    description: str
    reason: str
    nutrition_tags: NutritionTags
    estimated_cost: Optional[float] = None
    estimated_duration_minutes: Optional[int] = None


class AlternativeDeliveryItem(BaseModel):
    provider_name: str
    dish_name_or_category: str
    reason: str
    nutrition_tags: NutritionTags
    estimated_cost: Optional[float] = None
    estimated_duration_minutes: Optional[int] = None


class MainRecommendationDineIn(BaseModel):
    provider_name: str
    dish_name_or_category: Union[str, List[str]]
    description: str
    reason: str
    nutrition_tags: NutritionTags
    estimated_arrival_minutes: Optional[int] = None
    estimated_dine_duration_minutes: Optional[int] = None
    estimated_cost: Optional[float] = None


class AlternativeDineInItem(BaseModel):
    provider_name: str
    dish_name_or_category: Union[str, List[str]]
    reason: str
    nutrition_tags: NutritionTags
    estimated_cost: Optional[float] = None
    estimated_arrival_minutes: Optional[int] = None
    estimated_dine_duration_minutes: Optional[int] = None


class Ingredient(BaseModel):
    name: str
    amount: Optional[float] = None
    unit: Optional[str] = None
    notes: Optional[str] = None


class ReplacementSuggestion(BaseModel):
    missing_item: str
    replacement_name: str
    rationale: str


class MainRecommendationCook(BaseModel):
    recipe_name: str
    key_cooking_steps: List[str]
    ingredients: List[Ingredient]
    estimated_time_minutes: int
    servings_notes: Optional[str] = None
    replacement_suggestions: List[ReplacementSuggestion] = Field(min_items=2, max_items=2)
    reason: str
    nutrition_tags: NutritionTags


class AlternativeCookItem(BaseModel):
    recipe_name: str
    brief_description: str
    reason: str
    estimated_time_minutes: int
    nutrition_tags: NutritionTags


MainRecommendation = Union[MainRecommendationDelivery, MainRecommendationDineIn, MainRecommendationCook]
AlternativeItem = Union[AlternativeDeliveryItem, AlternativeDineInItem, AlternativeCookItem]


class Output(BaseModel):
    id: Optional[str] = None
    mode: Mode
    main_recommendation: MainRecommendation
    alternatives: List[AlternativeItem] = Field(min_items=2, max_items=3)
    response: str


# -----------------------------
# Memory store (local JSON)
# -----------------------------


@dataclass
class AgentConfig:
    api_key: str
    llm_name: str = "deepseek-chat"
    base_url: str = "https://api.deepseek.com/v1"
    temperature: float = 0.0
    memory_path: Path = Path("memory.json")
    schemas_dir: Path = Path("schemas")


class LocalMemoryStore:
    def __init__(self, memory_path: Path):
        self.memory_path = memory_path

    def load(self, user_id: str) -> Dict[str, Any]:
        if not self.memory_path.exists():
            return {"user_id": user_id, "recent_items": [], "taste_profile": {}}
        data = json.loads(self.memory_path.read_text(encoding="utf-8"))
        return data.get(user_id, {"user_id": user_id, "recent_items": [], "taste_profile": {}})

    def save(self, user_id: str, memory: Dict[str, Any]) -> None:
        if self.memory_path.exists():
            data = json.loads(self.memory_path.read_text(encoding="utf-8"))
        else:
            data = {}
        data[user_id] = memory
        self.memory_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# -----------------------------
# Agent
# -----------------------------


class WhateverToEatAgent:
    def __init__(self, cfg: AgentConfig):
        self.cfg = cfg
        self.llm = ChatOpenAI(
            model=cfg.llm_name,
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            temperature=cfg.temperature,
        )

        self.user_parser = PydanticOutputParser(pydantic_object=UserInput)
        self.output_parser = PydanticOutputParser(pydantic_object=Output)

        self.memory_store = LocalMemoryStore(cfg.memory_path)
        self._user_schema_text = self._load_text(cfg.schemas_dir / "UserInput.json")
        self._output_schema_text = self._load_text(cfg.schemas_dir / "Output.json")

        # A single place to tweak the prompting strategy.
        self._query_rephrase_prefix = (
            "Given the user's natural language request, rewrite it into JSON that matches the "
            "schema below. Return ONLY JSON. Do not add any explanations.\n\n"
        )

    def _load_text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def _format_memory_for_prompt(self, memory: Dict[str, Any]) -> str:
        recent_items = memory.get("recent_items", [])
        taste_profile = memory.get("taste_profile", {})
        return json.dumps(
            {"recent_items": recent_items, "taste_profile": taste_profile},
            ensure_ascii=False,
            indent=2,
        )

    def normalize_input(self, raw_text: str) -> UserInput:
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self._query_rephrase_prefix + "UserInput.json schema:\n" + self._user_schema_text + "\n\n"
                 + "Format instructions:\n" + self.user_parser.get_format_instructions()),
                ("human", "Raw user input:\n{raw_text}"),
            ]
        )
        chain = prompt | self.llm | self.user_parser
        return chain.invoke({"raw_text": raw_text})

    def recommend(self, user_input: UserInput, user_id: str = "default") -> Output:
        memory = self.memory_store.load(user_id)
        memory_text = self._format_memory_for_prompt(memory)

        mode = user_input.mode

        # Branch hint so the model knows what to focus on.
        mode_hint = {
            "delivery": "delivery mode: recommend a restaurant + dish for delivery. Use location if provided.",
            "dine_in": "dine_in mode: recommend a restaurant + dish category for dine-in. Use location if provided.",
            "cook": "cook mode: recommend a recipe with ingredients, key steps, and replacement suggestions.",
        }[mode]

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are an assistant that recommends food. "
                    "Return ONLY JSON that matches Output.json.\n\n"
                    + "Output.json schema:\n"
                    + self._output_schema_text
                    + "\n\n"
                    + "Format instructions:\n"
                    + self.output_parser.get_format_instructions()
                    + "\n\n"
                    + "Mode hint:\n"
                    + mode_hint,
                ),
                (
                    "human",
                    "UserInput (JSON):\n{user_input_json}\n\n"
                    "Local memory (JSON):\n{memory_json}\n\n"
                    "Rules:\n"
                    "- Avoid recent_items duplication when possible.\n"
                    "- Respect constraints/diet_restrictions.\n"
                    "- Provide 1 main recommendation + 2-3 alternatives.\n"
                    "- Ensure the output fields are valid JSON only.",
                ),
            ]
        )

        chain = prompt | self.llm | self.output_parser
        user_input_json = user_input.json(ensure_ascii=False)
        output = chain.invoke({"user_input_json": user_input_json, "memory_json": memory_text})
        return output

    def update_memory(self, user_id: str, user_input: UserInput, output: Output) -> None:
        memory = self.memory_store.load(user_id)
        recent_items = memory.get("recent_items", [])
        taste_profile = memory.get("taste_profile", {})

        # Update recent history with a simple "name" signal.
        main = output.main_recommendation
        main_name = getattr(main, "dish_name_or_category", None) or getattr(main, "recipe_name", None)
        if isinstance(main_name, list):
            main_name = main_name[0] if main_name else None
        if main_name:
            recent_items = [main_name] + recent_items
        memory["recent_items"] = recent_items[:50]

        # Update taste profile signals (store raw user preferences).
        for key in ["liked_flavors", "disliked_flavors", "diet_restrictions", "rating_last", "constraints"]:
            val = getattr(user_input, key, None)
            if val is not None:
                taste_profile[key] = val
        memory["taste_profile"] = taste_profile

        self.memory_store.save(user_id, memory)

    def run(self, raw_text: str, user_id: str = "default") -> Output:
        user_input = self.normalize_input(raw_text)
        output = self.recommend(user_input, user_id=user_id)
        self.update_memory(user_id, user_input, output)
        return output

