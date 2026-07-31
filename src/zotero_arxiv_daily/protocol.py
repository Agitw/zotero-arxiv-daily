from dataclasses import dataclass
from typing import Optional, TypeVar
from datetime import datetime
import re
import tiktoken
from openai import OpenAI
from loguru import logger
import json
RawPaperItem = TypeVar('RawPaperItem')


def is_chinese_language(language: str | None) -> bool:
    return str(language or "").lower() in {"chinese", "zh", "zh-cn", "中文"}


TLDR_FIELDS = (
    ("research_problem", "研究问题"),
    ("solution_approach", "解决思路"),
    ("core_method", "核心方法"),
    ("key_results", "关键结果"),
    ("main_conclusion", "主要结论"),
)
TLDR_MISSING = "摘要未说明"


def _json_object_from_text(text: str | None) -> dict:
    match = re.search(r"\{.*\}", text or "", flags=re.DOTALL)
    if match is None:
        return {}
    try:
        value = json.loads(match.group(0))
    except (json.JSONDecodeError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def format_structured_tldr(text: str | None) -> str:
    data = _json_object_from_text(text)
    if not data:
        for _, label in TLDR_FIELDS:
            match = re.search(
                rf"(?:^|\n)\s*(?:[-*]\s*)?{re.escape(label)}[：:]\s*(.+)",
                text or "",
            )
            if match:
                data[label] = match.group(1).strip()
    lines = []
    for key, label in TLDR_FIELDS:
        value = data.get(key, data.get(label, TLDR_MISSING))
        if not isinstance(value, str) or not value.strip():
            value = TLDR_MISSING
        lines.append(f"{label}：{value.strip()}")
    return "\n".join(lines)


def format_affiliations(
    first_affiliation: str | None,
    corresponding_affiliations: list[str] | None,
) -> list[str] | None:
    first = str(first_affiliation or "").strip()
    corresponding = []
    for value in corresponding_affiliations or []:
        affiliation = str(value or "").strip()
        if affiliation and affiliation not in corresponding:
            corresponding.append(affiliation)
    if first and corresponding == [first]:
        return [f"第一及通讯单位：{first}"]
    result = [f"第一单位：{first}"] if first else []
    result.extend(
        f"通讯单位：{affiliation}"
        for affiliation in corresponding
        if affiliation != first
    )
    return result or None


@dataclass
class Paper:
    source: str
    title: str
    authors: list[str]
    abstract: str
    url: str
    pdf_url: Optional[str] = None
    full_text: Optional[str] = None
    venue: Optional[str] = None
    published_date: Optional[str] = None
    tldr: Optional[str] = None
    affiliations: Optional[list[str]] = None
    score: Optional[float] = None
    matched_zotero_titles: Optional[list[str]] = None
    recommendation_reason: Optional[str] = None
    doi: Optional[str] = None
    external_id: Optional[str] = None
    venue_issns: Optional[list[str]] = None
    llm_selection_reason: Optional[str] = None
    embedding_score: Optional[float] = None
    deepseek_score: Optional[float] = None
    score_source: Optional[str] = None
    llm_scoring_attempted: bool = False
    llm_scoring_succeeded: bool = False
    venue_bonus: float = 0.0

    def _generate_tldr_with_llm(self, openai_client:OpenAI,llm_params:dict) -> str:
        lang = llm_params.get('language', 'English')
        use_chinese = is_chinese_language(lang)
        if use_chinese:
            prompt = (
                "请只根据以下标题和摘要整理中文论文解读。不得根据常识补全摘要没有提供的信息。\n"
                "返回一个 JSON 对象且不要添加其他文字，必须包含以下字符串字段："
                "research_problem（研究问题）、solution_approach（解决思路）、"
                "core_method（核心方法）、key_results（关键结果）、"
                "main_conclusion（主要结论）。"
                "每项使用 1-2 句；若摘要没有提供对应信息，字段值必须写“摘要未说明”。\n\n"
            )
            system_prompt = (
                "你是严谨的科研论文解读助手。只依据提供的标题和摘要，用中文返回指定 JSON。"
            )
        else:
            prompt = (
                f"Use only the title and abstract to summarize this paper in {lang}. "
                "Do not infer facts absent from the abstract. Return one JSON object with "
                "the string fields research_problem, solution_approach, core_method, "
                "key_results, and main_conclusion. Use '摘要未说明' when the abstract "
                "does not provide a field. Return JSON only.\n\n"
            )
            system_prompt = (
                "You are a precise scientific paper analyst. Return only the requested JSON "
                f"in {lang}."
            )
        if self.title:
            prompt += f"Title:\n {self.title}\n\n"

        if self.abstract:
            prompt += f"Abstract: {self.abstract}\n\n"

        if not self.abstract:
            logger.warning(f"No abstract is provided for {self.url}")
            return "Failed to generate TLDR. No abstract is provided"
        
        # use gpt-4o tokenizer for estimation
        enc = tiktoken.encoding_for_model("gpt-4o")
        prompt_tokens = enc.encode(prompt)
        prompt_tokens = prompt_tokens[:4000]  # truncate to 4000 tokens
        prompt = enc.decode(prompt_tokens)
        
        response = openai_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {"role": "user", "content": prompt},
            ],
            **llm_params.get('generation_kwargs', {})
        )
        return format_structured_tldr(response.choices[0].message.content)
    
    def generate_tldr(self, openai_client:OpenAI,llm_params:dict) -> str:
        try:
            tldr = self._generate_tldr_with_llm(openai_client,llm_params)
            self.tldr = tldr
            return tldr
        except Exception as e:
            logger.warning(f"Failed to generate tldr of {self.url}: {e}")
            tldr = format_structured_tldr(None)
            self.tldr = tldr
            return tldr

    def _generate_affiliations_with_llm(self, openai_client:OpenAI,llm_params:dict) -> Optional[list[str]]:
        if self.full_text is not None:
            prompt = (
                "From the beginning of this paper, extract only the first author's primary "
                "affiliation and the corresponding author's primary affiliation(s). Return "
                "JSON only with this shape: "
                '{"first_affiliation":"", "corresponding_affiliations":[]}. '
                "Do not infer an affiliation that is not explicitly present.\n\n"
                f"{self.full_text}"
            )
            # use gpt-4o tokenizer for estimation
            enc = tiktoken.encoding_for_model("gpt-4o")
            prompt_tokens = enc.encode(prompt)
            prompt_tokens = prompt_tokens[:2000]  # truncate to 2000 tokens
            prompt = enc.decode(prompt_tokens)
            generation_kwargs = dict(llm_params.get('generation_kwargs', {}))
            generation_kwargs.update(llm_params.get('affiliation_generation_kwargs', {}))
            affiliations = openai_client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You extract first-author and corresponding-author affiliations and return JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                **generation_kwargs
            )
            data = _json_object_from_text(affiliations.choices[0].message.content)
            first = str(data.get("first_affiliation") or "").strip()
            corresponding_value = data.get("corresponding_affiliations") or []
            if isinstance(corresponding_value, str):
                corresponding_value = [corresponding_value]
            return format_affiliations(
                first,
                corresponding_value if isinstance(corresponding_value, list) else [],
            )
    
    def generate_affiliations(self, openai_client:OpenAI,llm_params:dict) -> Optional[list[str]]:
        if self.affiliations:
            return self.affiliations
        try:
            affiliations = self._generate_affiliations_with_llm(openai_client,llm_params)
            self.affiliations = affiliations
            return affiliations
        except Exception as e:
            logger.warning(f"Failed to generate affiliations of {self.url}: {e}")
            self.affiliations = None
            return None
@dataclass
class CorpusPaper:
    title: str
    abstract: str
    added_date: datetime
    paths: list[str]
