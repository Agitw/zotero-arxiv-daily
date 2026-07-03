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


def contains_cjk(text: str | None) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def chinese_tldr_unavailable_message() -> str:
    return "摘要生成暂不可用，请打开论文链接查看原文。"


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

    def _generate_tldr_with_llm(self, openai_client:OpenAI,llm_params:dict) -> str:
        lang = llm_params.get('language', 'English')
        use_chinese = is_chinese_language(lang)
        if use_chinese:
            prompt = (
                "请根据以下论文信息生成中文速览。\n"
                "使用 3-4 个要点，覆盖：核心问题、方法或模型、关键结果，"
                "以及它为什么可能对用户的研究有价值。避免夸张表述，内容要具体对应论文。\n\n"
            )
            system_prompt = (
                "你是一个擅长快速阅读科研论文的中文助手。请始终用中文回答，"
                "用清晰、具体的要点概括论文的核心信息。"
            )
        else:
            prompt = (
                f"Given the following information of a paper, generate a TLDR in {lang}.\n"
                "Use 3-4 concise bullet points covering: the core problem, method or model, "
                "key result, and why it matters to the user's research. Avoid hype and keep "
                "the summary specific to the paper.\n\n"
            )
            system_prompt = (
                "You are an assistant who perfectly summarizes scientific paper, and gives "
                f"the core idea of the paper to the user. Your answer should be in {lang}."
            )
        if self.title:
            prompt += f"Title:\n {self.title}\n\n"

        if self.abstract:
            prompt += f"Abstract: {self.abstract}\n\n"

        if self.full_text:
            prompt += f"Preview of main content:\n {self.full_text}\n\n"

        if not self.full_text and not self.abstract:
            logger.warning(f"Neither full text nor abstract is provided for {self.url}")
            return "Failed to generate TLDR. Neither full text nor abstract is provided"
        
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
        tldr = response.choices[0].message.content
        if use_chinese and not contains_cjk(tldr):
            tldr = self._rewrite_tldr_in_chinese(openai_client, llm_params, tldr)
        return tldr

    def _rewrite_tldr_in_chinese(self, openai_client: OpenAI, llm_params: dict, tldr: str) -> str:
        response = openai_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "你是科研论文速览助手。请只用中文回答，不要保留英文整句。",
                },
                {
                    "role": "user",
                    "content": (
                        "请将以下 TLDR 改写为中文，保留具体科研含义，使用简洁的 3-4 个要点或一段短摘要：\n\n"
                        f"{tldr}"
                    ),
                },
            ],
            **llm_params.get('generation_kwargs', {})
        )
        rewritten = response.choices[0].message.content or ""
        if not contains_cjk(rewritten):
            return chinese_tldr_unavailable_message()
        return rewritten
    
    def generate_tldr(self, openai_client:OpenAI,llm_params:dict) -> str:
        try:
            tldr = self._generate_tldr_with_llm(openai_client,llm_params)
            self.tldr = tldr
            return tldr
        except Exception as e:
            logger.warning(f"Failed to generate tldr of {self.url}: {e}")
            if is_chinese_language(llm_params.get("language")):
                tldr = chinese_tldr_unavailable_message()
            else:
                tldr = self.abstract
            self.tldr = tldr
            return tldr

    def _generate_affiliations_with_llm(self, openai_client:OpenAI,llm_params:dict) -> Optional[list[str]]:
        if self.full_text is not None:
            prompt = f"Given the beginning of a paper, extract the affiliations of the authors in a python list format, which is sorted by the author order. If there is no affiliation found, return an empty list '[]':\n\n{self.full_text}"
            # use gpt-4o tokenizer for estimation
            enc = tiktoken.encoding_for_model("gpt-4o")
            prompt_tokens = enc.encode(prompt)
            prompt_tokens = prompt_tokens[:2000]  # truncate to 2000 tokens
            prompt = enc.decode(prompt_tokens)
            affiliations = openai_client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You are an assistant who perfectly extracts affiliations of authors from a paper. You should return a python list of affiliations sorted by the author order, like [\"TsingHua University\",\"Peking University\"]. If an affiliation is consisted of multi-level affiliations, like 'Department of Computer Science, TsingHua University', you should return the top-level affiliation 'TsingHua University' only. Do not contain duplicated affiliations. If there is no affiliation found, you should return an empty list [ ]. You should only return the final list of affiliations, and do not return any intermediate results.",
                    },
                    {"role": "user", "content": prompt},
                ],
                **llm_params.get('generation_kwargs', {})
            )
            affiliations = affiliations.choices[0].message.content

            affiliations = re.search(r'\[.*?\]', affiliations, flags=re.DOTALL).group(0)
            affiliations = json.loads(affiliations)
            affiliations = list(set(affiliations))
            affiliations = [str(a) for a in affiliations]

            return affiliations
    
    def generate_affiliations(self, openai_client:OpenAI,llm_params:dict) -> Optional[list[str]]:
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
