"""Orchestration: user text -> provider -> policy -> one fixed executor."""
from dataclasses import dataclass
import logging

from actions.action_models import AIReply
from actions.action_executor import ActionExecutor
from actions.action_registry import Level
from ai.base_provider import AIProvider
from security.security_manager import Decision, SecurityManager
from utils.logger import safe_transcript


@dataclass(frozen=True)
class Prepared:
    reply: AIReply
    decision: Decision | None
    target_hwnd: int


class AssistantService:
    def __init__(self, provider: AIProvider, security: SecurityManager, executor: ActionExecutor, logger: logging.Logger, learning_mode: bool):
        self.provider = provider
        self.security = security
        self.executor = executor
        self.logger = logger
        self.learning_mode = learning_mode
        self.history: list[tuple[str, str]] = []

    def prepare(self, utterance: str, context: str, target_hwnd: int, focused_control: str = "") -> Prepared:
        self.logger.info("Reconocido: %s", safe_transcript(utterance))
        reply = self.provider.interpret(utterance, context, self.history, self.learning_mode)
        if reply.type == "response":
            self.history.append((utterance, reply.spoken_response))
            self.history = self.history[-3:]
            return Prepared(reply, None, target_hwnd)
        decision = self.security.evaluate(reply, context, focused_control)
        self.logger.info("Solicitada: %s; nivel: %s", reply.action, decision.level.name)
        if decision.level == Level.BLOCKED:
            self.logger.warning("Bloqueada: %s", reply.action)
        return Prepared(reply, decision, target_hwnd)

    def execute(self, prepared: Prepared, utterance: str) -> str:
        if prepared.decision is None:
            return prepared.reply.spoken_response
        if prepared.decision.level == Level.BLOCKED:
            return prepared.decision.reason
        if prepared.reply.action == "get_screen_description":
            result = self.executor.execute(prepared.reply, prepared.target_hwnd, utterance)
        else:
            result = self.executor.execute(prepared.reply, prepared.target_hwnd)
        self.logger.info("Ejecutada: %s", prepared.reply.action)
        self.history.append((safe_transcript(utterance), result))
        self.history = self.history[-3:]
        return result
