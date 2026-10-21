import json
from typing import ClassVar

import structlog
from pydantic import BaseModel, ValidationError

from app.models import StrategyProfile
from app.services.llm.base import LLMMessage, LLMProvider

logger = structlog.get_logger()


class ChatResult(BaseModel):
    kind: str
    message: str
    preview: dict | None = None


class ReflectionCritique(BaseModel):
    passed: bool = True
    issues: list[str] = []
    must_revise: bool = False


def _strip_code_fence(content: str) -> str:
    text = content.strip().lstrip("\ufeff")
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _decode_json_value(content: str):
    text = _strip_code_fence(content)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for index, character in enumerate(text):
        if character not in "[{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, (dict, list, str)):
            return value
    return None


def _extract_json_string(text: str, key: str) -> str | None:
    marker = f'"{key}"'
    marker_index = text.find(marker)
    if marker_index < 0:
        return None
    colon_index = text.find(":", marker_index + len(marker))
    if colon_index < 0:
        return None
    start = text.find('"', colon_index + 1)
    if start < 0:
        return None

    escaped = False
    index = start + 1
    while index < len(text):
        character = text[index]
        if character == '"' and not escaped:
            break
        if character == "\\" and not escaped:
            escaped = True
        else:
            escaped = False
        index += 1
    if index >= len(text):
        return None

    raw = text[start + 1 : index]
    escaped_newlines = raw.replace("\r", "\\r").replace("\n", "\\n")
    try:
        return json.loads(f'"{escaped_newlines}"')
    except json.JSONDecodeError:
        return (
            raw.replace("\\n", "\n")
            .replace("\\r", "\r")
            .replace("\\t", "\t")
            .replace('\\"', '"')
        )


def _recover_chat_fields(content: str) -> dict | None:
    text = _strip_code_fence(content)
    message = _extract_json_string(text, "message")
    if message is None:
        return None
    kind = _extract_json_string(text, "kind") or "analysis"
    return {"kind": kind, "message": message}


def _parse_model_payload(content: str) -> dict | None:
    value = _decode_json_value(content)
    if value is None:
        return _recover_chat_fields(content)
    for _ in range(3):
        if isinstance(value, dict):
            return value
        if not isinstance(value, str) or not value.strip():
            return None
        nested = _decode_json_value(value)
        if nested == value:
            return None
        value = nested
    return None


def _parse_critique(content: str) -> ReflectionCritique | None:
    value = _decode_json_value(content)
    if not isinstance(value, dict):
        return None
    if not any(key in value for key in ("passed", "issues", "must_revise")):
        return None
    raw_issues = value.get("issues") or []
    if isinstance(raw_issues, str):
        raw_issues = [raw_issues]
    issues = [str(item).strip() for item in raw_issues if str(item).strip()]
    must_revise = bool(value.get("must_revise"))
    passed_value = value.get("passed")
    passed = bool(passed_value) if passed_value is not None else not issues
    if must_revise:
        passed = False
    return ReflectionCritique(
        passed=passed,
        issues=issues,
        must_revise=must_revise or not passed or bool(issues),
    )


class Orchestrator:
    ALLOWED_KINDS: ClassVar[set[str]] = {"analysis", "recommendation", "question", "error"}

    def __init__(self, llm: LLMProvider, max_revision_attempts: int = 1) -> None:
        self.llm = llm
        self.max_revision_attempts = max(0, max_revision_attempts)

    def _parse_result(self, content: str) -> ChatResult:
        payload = _parse_model_payload(content)
        if payload is not None:
            try:
                result = ChatResult.model_validate(payload)
            except ValidationError:
                result = None
            if result is not None:
                if result.kind not in self.ALLOWED_KINDS:
                    return ChatResult(kind="error", message="模型返回了不支持的操作类型。")
                return result

        text = content.strip()
        if text:
            return ChatResult(kind="analysis", message=text)
        return ChatResult(kind="error", message="模型返回格式无效，请重试。")

    def _draft_context(
        self,
        profile: StrategyProfile | None,
        learning_context: dict | None,
        read_only_context: dict | None,
        persona: str | None,
    ) -> str:
        if profile is None:
            strategy_context = "当前投放策略：未配置；目标=未配置；约束={}"
        else:
            strategy_context = (
                f"当前投放策略 v{profile.version}: {profile.business_direction}; "
                f"{profile.primary_objective}; 约束={profile.hard_constraints}"
            )
        return (
            (f"{persona}; " if persona else "")
            + f"{strategy_context}; "
            f"learning_context={json.dumps(learning_context, ensure_ascii=False, default=str)}; "
            f"read_only_context={json.dumps(read_only_context, ensure_ascii=False, default=str)}; "
            '请优先输出 JSON：{"kind":"analysis|recommendation|question|error",'
            '"message":"给用户看的中文回答","preview":null}。'
            "如果不方便输出 JSON，也可以直接输出自然语言分析。"
        )

    def _critic_messages(
        self,
        base_context: str,
        question: str,
        draft: ChatResult,
    ) -> list[LLMMessage]:
        system = (
            base_context
            + "\n\n你现在是严格的直播运营 Critic，不负责重新回答，只负责审查草稿。\n"
            "必须检查：\n"
            "1. 数字、时间、阈值是否都能在给定上下文中找到，不能编造。\n"
            "2. 每个判断是否有明确依据，是否把现象误写成原因。\n"
            "3. 是否混用了综合营销 ROI、素材 ROI、支付 ROI 等口径。\n"
            "4. 调整方案是否写清谁做、何时做、具体动作、成功标准和止损条件。\n"
            "5. 是否违反只读边界，是否把建议说成已执行。\n"
            "6. 是否直接回答用户问题，是否存在空话、重复或过度推断。\n"
            "只输出 JSON：{\"passed\":true|false,\"issues\":[\"具体问题\"],"
            "\"must_revise\":true|false}。宁可指出具体问题，不要笼统说“可以优化”。"
        )
        user = (
            f"用户问题：\n{question or '用户上传了图片，请结合图片回答。'}\n\n"
            f"待审草稿：\n{draft.message}"
        )
        return [LLMMessage(role="system", content=system), LLMMessage(role="user", content=user)]

    def _revision_messages(
        self,
        base_context: str,
        question: str,
        draft: ChatResult,
        critique: ReflectionCritique,
    ) -> list[LLMMessage]:
        issues = "\n".join(f"- {item}" for item in critique.issues) or "- Critic 判定未通过"
        system = (
            base_context
            + "\n\n你现在负责修订草稿。必须逐条解决 Critic 指出的问题；"
            "不得新增上下文中没有的数字、时间、阈值或历史。"
            "如果原草稿没有证据，就明确写“没读到”，不要补猜。"
            "修订后仍按原 JSON 格式输出最终回答。"
        )
        user = (
            f"用户问题：\n{question or '用户上传了图片，请结合图片回答。'}\n\n"
            f"原草稿：\n{draft.message}\n\n"
            f"Critic 问题：\n{issues}\n\n"
            "请输出修订后的最终回答。"
        )
        return [LLMMessage(role="system", content=system), LLMMessage(role="user", content=user)]

    async def handle(
        self,
        message: str,
        profile: StrategyProfile | None,
        learning_context: dict | None = None,
        read_only_context: dict | None = None,
        persona: str | None = None,
        images: list[str] | None = None,
    ) -> ChatResult:
        """执行一次带 Reflection 的回答流程。

        初稿 → Critic → 必要时修订 → 返回最终结果。
        最多修订一次，避免无限自我循环和不可控调用成本。
        """
        context = self._draft_context(profile, learning_context, read_only_context, persona)
        user_content: str | list[dict] = message
        if images:
            user_content = [{"type": "text", "text": message or "帮我看下这张图片。"}]
            user_content.extend(
                {"type": "image_url", "image_url": {"url": url}} for url in images
            )

        response = await self.llm.complete(
            [
                LLMMessage(role="system", content=context),
                LLMMessage(role="user", content=user_content),
            ],
            tools=[],
        )
        draft = self._parse_result(response.content)
        if (
            self.max_revision_attempts == 0
            or draft.kind not in {"analysis", "recommendation"}
            or not draft.message.strip()
        ):
            return draft

        critique: ReflectionCritique | None = None
        try:
            critic_response = await self.llm.complete(
                self._critic_messages(context, message, draft),
                tools=[],
            )
            critique = _parse_critique(critic_response.content)
        except Exception:  # noqa: BLE001
            logger.exception("orchestrator_reflection_critic_failed")
            return draft

        if critique is None:
            logger.warning("orchestrator_reflection_critic_unparseable")
            return draft
        if critique.passed and not critique.issues and not critique.must_revise:
            return draft

        try:
            revision_response = await self.llm.complete(
                self._revision_messages(context, message, draft, critique),
                tools=[],
            )
            revised = self._parse_result(revision_response.content)
        except Exception:  # noqa: BLE001
            logger.exception("orchestrator_reflection_revision_failed")
            return draft

        if revised.kind == "error" or not revised.message.strip():
            logger.warning("orchestrator_reflection_revision_invalid")
            return draft
        logger.info(
            "orchestrator_reflection_revised",
            issue_count=len(critique.issues),
            must_revise=critique.must_revise,
        )
        return revised
