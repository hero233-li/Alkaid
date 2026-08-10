from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, TypeVar

from apps.utils.product_Conf.catalog import ProductExecutionSnapshot, ProductWorkflowStep
from apps.workflow.product_applications.contracts import SubmittedApplication
from apps.workflow.product_applications.modules import (
    ApplicationModuleOutcome,
    IdentityModuleOutcome,
    execute_application_module,
    execute_identity_module,
)
from apps.workflow.product_applications.validation import ProductConfigurationError

T = TypeVar("T")
ModuleExecutor = Callable[["WorkflowExecutionContext", Mapping[str, Any]], object]


class ProductWorkflowConfigurationError(ProductConfigurationError):
    pass


@dataclass(frozen=True, slots=True)
class ModuleDefinition:
    code: str
    version: int
    execute: ModuleExecutor
    requires: frozenset[str] = frozenset()
    provides: frozenset[str] = frozenset()
    parameters: frozenset[str] = frozenset()


@dataclass(slots=True)
class WorkflowExecutionContext:
    runtime: Any
    snapshot: ProductExecutionSnapshot
    payload: Mapping[str, Any]
    application_link_kind: str
    progress: Callable[..., None] | None = None
    outputs: dict[str, object] = field(default_factory=dict)

    def publish(self, name: str, value: object) -> None:
        if name in self.outputs:
            raise RuntimeError(f"产品流程输出重复：{name}")
        self.outputs[name] = value

    def require(self, name: str, expected_type: type[T]) -> T:
        value = self.outputs.get(name)
        if value is None:
            raise RuntimeError(f"产品流程缺少前序输出：{name}")
        if not isinstance(value, expected_type):
            raise RuntimeError(f"产品流程输出类型错误：{name}，期望 {expected_type.__name__}")
        return value

    def optional(self, name: str, expected_type: type[T]) -> T | None:
        value = self.outputs.get(name)
        if value is None:
            return None
        if not isinstance(value, expected_type):
            raise RuntimeError(f"产品流程输出类型错误：{name}，期望 {expected_type.__name__}")
        return value


def _execute_application(
    context: WorkflowExecutionContext, parameters: Mapping[str, Any]
) -> object:
    outcome = execute_application_module(
        runtime=context.runtime,
        snapshot=context.snapshot,
        payload=context.payload,
        application_link_kind=context.application_link_kind,
        progress=context.progress,
    )
    context.publish("application", outcome)
    context.publish("submitted_application", outcome.submitted_application)
    return outcome


def _execute_identity(context: WorkflowExecutionContext, parameters: Mapping[str, Any]) -> object:
    submitted_application = context.require("submitted_application", SubmittedApplication)
    outcome = execute_identity_module(
        runtime=context.runtime,
        payload=context.payload,
        environment=context.snapshot.environment,
        submitted_application=submitted_application,
        progress=context.progress,
    )
    context.publish("identity", outcome)
    return outcome


MODULE_REGISTRY: dict[str, ModuleDefinition] = {
    "application.apply": ModuleDefinition(
        code="application.apply",
        version=1,
        execute=_execute_application,
        provides=frozenset({"application", "submitted_application"}),
    ),
    "identity.verify": ModuleDefinition(
        code="identity.verify",
        version=1,
        execute=_execute_identity,
        requires=frozenset({"submitted_application"}),
        provides=frozenset({"identity"}),
    ),
}


def validate_product_workflow(steps: tuple[ProductWorkflowStep, ...]) -> None:
    available: set[str] = set()
    for step in steps:
        definition = MODULE_REGISTRY.get(step.module)
        if definition is None:
            raise ProductWorkflowConfigurationError(
                f"产品流程步骤 {step.step_id} 引用了未知模块：{step.module}"
            )
        if step.version != definition.version:
            raise ProductWorkflowConfigurationError(
                f"产品流程模块版本不受支持：{step.module}@{step.version}；"
                f"当前版本={definition.version}"
            )
        unknown_parameters = set(step.parameters) - definition.parameters
        if unknown_parameters:
            raise ProductWorkflowConfigurationError(
                f"产品流程步骤 {step.step_id} 包含未知参数：{', '.join(sorted(unknown_parameters))}"
            )
        missing = definition.requires - available
        if missing:
            raise ProductWorkflowConfigurationError(
                f"产品流程步骤 {step.step_id} 缺少前序输出：{', '.join(sorted(missing))}"
            )
        overlapping = definition.provides & available
        if overlapping:
            raise ProductWorkflowConfigurationError(
                f"产品流程步骤 {step.step_id} 重复产生输出：{', '.join(sorted(overlapping))}"
            )
        available.update(definition.provides)
    if "application" not in available:
        raise ProductWorkflowConfigurationError("产品申请流程必须包含 application.apply 模块")


def execute_product_workflow(context: WorkflowExecutionContext) -> None:
    validate_product_workflow(context.snapshot.workflow)
    for step in context.snapshot.workflow:
        definition = MODULE_REGISTRY[step.module]
        definition.execute(context, step.parameters)


__all__ = (
    "ApplicationModuleOutcome",
    "IdentityModuleOutcome",
    "ProductWorkflowConfigurationError",
    "WorkflowExecutionContext",
    "execute_product_workflow",
    "validate_product_workflow",
)
